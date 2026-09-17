import logging

from ACI_backend.ACIApp.models import Requirement, RequirementPullRequest
from ACI_backend.integrations.jira.client import JiraAPIError
from ACI_backend.integrations.jira.utils import extract_jira_issue_keys

logger = logging.getLogger(__name__)


def ingest_jira_requirement(
    *,
    pull_request,
    jira_issue,
):
    """
    Create or update a Requirement from a Jira issue
    and associate it with a PullRequest.
    """

    issue_key = jira_issue["key"]
    fields = jira_issue.get("fields", {})

    status_data = fields.get("status") or {}

    status_name = status_data.get("name", "").lower()

    status_mapping = {
        "to do": "open",
        "open": "open",
        "in progress": "in_progress",
        "done": "completed",
        "closed": "completed",
        "cancelled": "cancelled",
        "canceled": "cancelled",
    }

    status = status_mapping.get(status_name, "open")

    repository = pull_request.repository

    requirement, _ = Requirement.objects.update_or_create(
        repository=repository,
        source="jira",
        external_id=issue_key,
        defaults={
            "title": fields.get("summary", ""),
            "description": fields.get("description") or "",
            "status": status,
        },
    )

    RequirementPullRequest.objects.get_or_create(
        requirement=requirement,
        pull_request=pull_request,
    )

    return requirement

def ingest_jira_requirements_for_pull_request(
    *,
    pull_request,
    text,
    jira_client,
):
    """
    Find Jira issue references in pull request text,
    retrieve those issues, and persist their requirements.
    """

    issue_keys = extract_jira_issue_keys(text)

    requirements = []

    for issue_key in issue_keys:
        try:
            jira_issue = jira_client.get_issue(issue_key)
        except JiraAPIError:
            logger.warning(
                "Skipping Jira requirement %s for pull request %s because the issue could not be fetched.",
                issue_key,
                pull_request,
                exc_info=True,
            )
            continue

        requirement = ingest_jira_requirement(
            pull_request=pull_request,
            jira_issue=jira_issue,
        )

        requirements.append(requirement)

    return requirements