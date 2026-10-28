import logging
import re

from django.conf import settings
from django.db import transaction

from ACI_backend.ACIApp.models import (
    ChangedFile,
    Commit,
    PullRequest,
    Repository,
    Requirement,
)
from ACI_backend.integrations.github.accounts import (
    link_repository_github_members,
)
from ACI_backend.integrations.github.client import GitHubClient
from ACI_backend.integrations.jira.client import JiraAPIError, JiraClient
from ACI_backend.integrations.jira.service import (
    ingest_jira_requirements_for_pull_request,
)
from ACI_backend.integrations.verification.service import (
    invalidate_evidence_for_changed_file,
    ingest_github_evidence,
    start_initial_verification,
)
from ACI_backend.integrations.verification.criteria import (
    sync_requirement_criteria_from_text,
)


logger = logging.getLogger(__name__)
GITHUB_ISSUE_REFERENCE = re.compile(r"(?<![\w/])#(\d+)\b")


def ingest_jira_links_for_pull_request(*, pull_request, payload):
    """Link Jira requirements referenced by a PR when Jira is configured."""

    if not settings.JIRA_BASE_URL or not settings.JIRA_API_TOKEN:
        return []
    pull_request_data = payload.get("pull_request", {})
    text = "\n".join(
        value
        for value in (
            pull_request_data.get("title", ""),
            pull_request_data.get("body", "") or "",
        )
        if isinstance(value, str)
    )
    if not text.strip():
        return []
    try:
        return ingest_jira_requirements_for_pull_request(
            pull_request=pull_request,
            text=text,
            jira_client=JiraClient(),
        )
    except JiraAPIError:
        logger.exception(
            "Jira requirement ingestion failed for %s",
            pull_request,
        )
        return []


def link_pull_request_requirements(*, pull_request, payload, github_client):
    """Link manual requirements and same-repository GitHub issues referenced by a PR."""

    pull_request_data = payload.get("pull_request", {})
    title = pull_request_data.get("title", "")
    body = pull_request_data.get("body", "") or ""
    text = "\n".join(value for value in (title, body) if isinstance(value, str))
    normalized_text = " ".join(text.casefold().split())
    repository = pull_request.repository
    linked = []

    for requirement in repository.requirements.all():
        external_id = requirement.external_id.strip()
        title_match = " ".join(requirement.title.casefold().split())
        external_match = bool(
            external_id
            and re.search(
                rf"(?<![A-Za-z0-9]){re.escape(external_id)}(?![A-Za-z0-9])",
                text,
                flags=re.IGNORECASE,
            )
        )
        title_match_found = len(title_match) >= 6 and title_match in normalized_text
        if external_match or title_match_found:
            linked.append(requirement)

    issue_numbers = sorted(
        {int(match.group(1)) for match in GITHUB_ISSUE_REFERENCE.finditer(text)}
    )
    for issue_number in issue_numbers:
        requirement = repository.requirements.filter(
            external_id__in=[str(issue_number), f"#{issue_number}"],
        ).first()
        if requirement is None:
            issue = github_client.get_issue(
                repository.owner,
                repository.name,
                issue_number,
            )
            if "pull_request" in issue:
                continue
            issue_title = issue.get("title")
            issue_body = issue.get("body") or ""
            if not isinstance(issue_title, str) or not issue_title.strip():
                raise ValueError(
                    f"GitHub issue #{issue_number} has no usable title."
                )
            requirement, _ = Requirement.objects.update_or_create(
                repository=repository,
                source="github",
                external_id=str(issue_number),
                defaults={
                    "title": issue_title,
                    "description": issue_body,
                    "url": issue.get("html_url", ""),
                    "status": (
                        "completed"
                        if issue.get("state") == "closed"
                        else "open"
                    ),
                },
            )
            if issue_body:
                sync_requirement_criteria_from_text(
                    requirement=requirement,
                    text=issue_body,
                )
        linked.append(requirement)

    for requirement in {item.id: item for item in linked}.values():
        pull_request.requirement_links.get_or_create(requirement=requirement)
    return list({item.id: item for item in linked}.values())


@transaction.atomic
def process_pull_request_event(payload):
    """
    Process a GitHub pull_request webhook payload.

    Creates or updates the Repository and PullRequest records,
    then retrieves and persists the PR commits.
    """

    if not isinstance(payload, dict):
        return []
    repository_data = payload.get("repository")
    if not isinstance(repository_data, dict) or "id" not in repository_data:
        return []
    pull_request_data = payload["pull_request"]

    # ---------------------------------------------------------
    # 1. Create or update repository
    # ---------------------------------------------------------

    repository_defaults = {
        "owner": repository_data["owner"]["login"],
        "name": repository_data["name"],
        "full_name": repository_data["full_name"],
        "default_branch": repository_data["default_branch"],
    }
    installation = payload.get("installation")
    if isinstance(installation, dict) and isinstance(installation.get("id"), int):
        repository_defaults["github_installation_id"] = installation["id"]

    repository, _ = Repository.objects.update_or_create(
        github_id=repository_data["id"],
        defaults=repository_defaults,
    )

    # ---------------------------------------------------------
    # 2. Create or update pull request
    # ---------------------------------------------------------

    pull_request, _ = PullRequest.objects.update_or_create(
        repository=repository,
        number=pull_request_data["number"],
        defaults={
            "github_id": pull_request_data["id"],
            "title": pull_request_data["title"],
            "author": pull_request_data["user"]["login"],
            "source_branch": pull_request_data["head"]["ref"],
            "target_branch": pull_request_data["base"]["ref"],
            "base_sha": pull_request_data["base"]["sha"],
            "head_sha": pull_request_data["head"]["sha"],
            "state": pull_request_data["state"],
            "is_merged": pull_request_data["merged"],
            "created_at": pull_request_data["created_at"],
            "updated_at": pull_request_data["updated_at"],
        },
    )
    link_repository_github_members(repository)

    ingest_jira_links_for_pull_request(
        pull_request=pull_request,
        payload=payload,
    )

    # ---------------------------------------------------------
    # 3. Retrieve commits from GitHub
    # ---------------------------------------------------------

    github_client = GitHubClient(
        token=settings.GITHUB_ACCESS_TOKEN or None,
        installation_id=repository.github_installation_id,
    )
    link_pull_request_requirements(
        pull_request=pull_request,
        payload=payload,
        github_client=github_client,
    )

    commits = github_client.get_pull_request_commits(
        owner=repository.owner,
        repository=repository.name,
        pull_request_number=pull_request.number,
    )

    # ---------------------------------------------------------
    # 4. Persist commits
    # ---------------------------------------------------------

    for commit_data in commits:
        commit, _ = Commit.objects.update_or_create(
            sha=commit_data["sha"],
            defaults={
                "repository": repository,
                "pull_request": pull_request,
                "message": commit_data["commit"]["message"],
                "author": commit_data["commit"]["author"]["name"],
                "committed_at": commit_data["commit"]["author"]["date"],
            },
        )

        # The pull-request commits endpoint does not include changed files.
        # Fetch the full commit so the change graph can be persisted and used
        # for evidence invalidation.
        github_commit = github_client.get_commit(
            owner=repository.owner,
            repository=repository.name,
            sha=commit.sha,
        )

        for changed_file in ingest_commit_files(
            commit=commit,
            github_commit=github_commit,
        ):
            invalidate_evidence_for_changed_file(changed_file)

    for requirement_link in pull_request.requirement_links.select_related(
        "requirement",
    ):
        try:
            start_initial_verification(
                requirement=requirement_link.requirement,
                pull_request=pull_request,
            )
        except ValueError:
            logger.warning(
                "Initial verification deferred for %s because no changed "
                "file is available yet.",
                pull_request,
            )

    if pull_request.requirement_links.exists():
        if repository.github_installation_id:
            from ACI_backend.integrations.github.outputs import (
                publish_delivery_result,
            )

            publish_delivery_result(pull_request)
        else:
            logger.warning(
                "GitHub delivery output was not published for %s because no "
                "GitHub App installation is linked.",
                pull_request,
            )

    return pull_request


def process_github_webhook(*, event, payload):
    """Dispatch a queued webhook event and schedule verification from new evidence."""

    if event == "pull_request":
        return process_pull_request_event(payload)
    if event in {"installation", "installation_repositories"}:
        return process_github_installation_event(event, payload)
    if event not in {"check_run", "status"}:
        return []

    if event == "check_run":
        check_run = payload.get("check_run", {})
        if (
            check_run.get("name") == "ACI / Delivery Verification"
            or payload.get("action") != "completed"
        ):
            return []
    elif payload.get("state") == "pending":
        return []

    evidence = process_github_evidence_event(event, payload, changed_only=True)
    if not evidence:
        return []

    pull_requests = {}
    for item in evidence:
        if item.pull_request_id:
            pull_requests[item.pull_request_id] = item.pull_request

    for pull_request in pull_requests.values():
        queued = False
        for requirement in pull_request.requirement_links.select_related(
            "requirement",
        ):
            try:
                start_initial_verification(
                    requirement=requirement.requirement,
                    pull_request=pull_request,
                )
                queued = True
            except ValueError:
                logger.warning(
                    "Verification deferred for %s because no changed file is available.",
                    pull_request,
                )
        if queued and pull_request.repository.github_installation_id:
            from ACI_backend.integrations.github.outputs import (
                publish_delivery_result,
            )

            publish_delivery_result(pull_request)
    return evidence


def ingest_commit_files(commit, github_commit):
    """
    Persist files changed by a GitHub commit.

    Uses update_or_create so repeated GitHub webhook deliveries
    do not create duplicate ChangedFile records.
    """

    files = github_commit.get("files", [])

    changed_files = []

    for file_data in files:
        changed_file, _ = ChangedFile.objects.update_or_create(
            commit=commit,
            filename=file_data["filename"],
            defaults={
                "status": file_data.get("status", ""),
                "additions": file_data.get("additions", 0),
                "deletions": file_data.get("deletions", 0),
                "changes": file_data.get("changes", 0),
                "patch": file_data.get("patch", ""),
            },
        )

        changed_files.append(changed_file)

    return changed_files


@transaction.atomic
def process_github_installation_event(event, payload):
    """Track repositories added to or removed from the GitHub App install."""

    installation = payload.get("installation")
    if not isinstance(installation, dict) or not isinstance(
        installation.get("id"), int
    ):
        raise ValueError("Invalid GitHub App installation payload.")
    installation_id = installation["id"]
    action = payload.get("action")

    if event == "installation" and action == "deleted":
        Repository.objects.filter(
            github_installation_id=installation_id,
        ).update(github_installation_id=None)
        return []

    if event == "installation_repositories" and action == "removed":
        removed = payload.get("repositories_removed", [])
        if not isinstance(removed, list):
            raise ValueError("Invalid removed repository list.")
        for repository_data in removed:
            if not isinstance(repository_data, dict) or not isinstance(
                repository_data.get("id"), int
            ):
                raise ValueError("Invalid removed repository.")
            Repository.objects.filter(
                github_id=repository_data["id"],
                github_installation_id=installation_id,
            ).update(github_installation_id=None)
        return []

    if event == "installation":
        if action != "created":
            return []
        repositories = payload.get("repositories", [])
    elif event == "installation_repositories" and action == "added":
        repositories = payload.get("repositories_added", [])
    else:
        return []

    if not isinstance(repositories, list):
        raise ValueError("Invalid added repository list.")
    saved_repositories = []
    for repository_data in repositories:
        owner = repository_data.get("owner") if isinstance(repository_data, dict) else None
        if (
            not isinstance(repository_data, dict)
            or not isinstance(repository_data.get("id"), int)
            or not isinstance(repository_data.get("name"), str)
            or not isinstance(repository_data.get("full_name"), str)
            or not isinstance(repository_data.get("default_branch"), str)
            or not isinstance(owner, dict)
            or not isinstance(owner.get("login"), str)
        ):
            raise ValueError("Invalid added repository.")
        repository, _ = Repository.objects.update_or_create(
            github_id=repository_data["id"],
            defaults={
                "owner": owner["login"],
                "name": repository_data["name"],
                "full_name": repository_data["full_name"],
                "default_branch": repository_data["default_branch"],
                "github_installation_id": installation_id,
            },
        )
        saved_repositories.append(repository)
    return saved_repositories


@transaction.atomic
def process_github_evidence_event(event, payload, *, changed_only=False):
    """Ingest a GitHub check or status event for linked requirements."""

    repository_data = payload["repository"]
    check_run = payload.get("check_run") if event == "check_run" else None
    if (
        isinstance(check_run, dict)
        and check_run.get("name") == "ACI / Delivery Verification"
    ):
        return []
    repository = Repository.objects.filter(
        github_id=repository_data["id"],
    ).first()
    if repository is None:
        return []
    if event == "check_run":
        check_run = payload.get("check_run")
        if not isinstance(check_run, dict):
            return []
        sha = check_run.get("head_sha")
    else:
        sha = payload.get("sha")
    if not sha:
        return []

    pull_request_number = None
    if event == "check_run":
        pull_requests = payload.get("check_run", {}).get("pull_requests", [])
        if pull_requests:
            pull_request_number = pull_requests[0].get("number")

    if pull_request_number:
        pull_request = PullRequest.objects.filter(
            repository=repository,
            number=pull_request_number,
        ).first()
    else:
        pull_request = PullRequest.objects.filter(
            repository=repository,
            head_sha=sha,
        ).first()
        if pull_request is None:
            commit = Commit.objects.filter(
                repository=repository,
                sha=sha,
                pull_request__isnull=False,
            ).select_related("pull_request").first()
            pull_request = commit.pull_request if commit else None
    if pull_request is None:
        return []

    commit, _ = Commit.objects.update_or_create(
        sha=sha,
        defaults={
            "repository": repository,
            "pull_request": pull_request,
            "message": "GitHub check/status result",
            "author": "github",
            "committed_at": pull_request.updated_at,
        },
    )
    return ingest_github_evidence(
        pull_request=pull_request,
        commit=commit,
        event=event,
        payload=payload,
        changed_only=changed_only,
    )
