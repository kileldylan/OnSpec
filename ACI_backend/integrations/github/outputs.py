import hashlib
import re
from urllib.parse import urlparse

from django.utils import timezone

from ACI_backend.ACIApp.models import (
    CriterionVerification,
    DeliveryDecision,
    RequirementCriterion,
)
from ACI_backend.integrations.github.client import (
    GitHubAPIError,
    GitHubClient,
)


CHECK_NAME = "ACI / Delivery Verification"
COMMENT_MARKER = "<!-- aci-delivery-verification -->"


def _latest_criterion_results(verification):
    results = CriterionVerification.objects.filter(
        verification=verification,
    ).order_by("criterion_id", "-evaluated_at", "-id")
    latest = {}
    for result in results:
        latest.setdefault(result.criterion_id, result)
    return latest


def _safe_markdown_text(value):
    value = str(value).replace("\r", " ").replace("\n", " ")
    return re.sub(r"([\\`*_{}\[\]()#+.!|<>])", r"\\\1", value)


def _evidence_reference(evidence):
    metadata = evidence.metadata if isinstance(evidence.metadata, dict) else {}
    url = metadata.get("source_url") or metadata.get("url")
    if isinstance(url, str):
        parsed = urlparse(url)
        if parsed.scheme == "https" and parsed.hostname == "github.com":
            safe_url = url.replace("(", "%28").replace(")", "%29")
            return f"[{evidence.status} evidence]({safe_url})"
    description = evidence.description.strip()
    return _safe_markdown_text(description) if description else "evidence recorded"


def build_delivery_report(pull_request):
    """Render the current, evidence-linked requirement decisions for GitHub."""

    links = pull_request.requirement_links.select_related("requirement").order_by(
        "requirement_id",
    )
    rows = []
    statuses = []
    for link in links:
        requirement = link.requirement
        verification = requirement.verifications.filter(
            pull_request=pull_request,
        ).first()
        if verification is None:
            rows.append(
                f"| {_safe_markdown_text(requirement.title)} | pending | "
                "| Awaiting verification |"
            )
            statuses.append("pending")
            continue

        decision = DeliveryDecision.objects.filter(
            verification=verification,
            is_current=True,
        ).first()
        has_active_run = verification.runs.filter(
            status__in=["queued", "running"],
        ).exists()
        is_pending = decision is None or has_active_run
        status = "pending" if is_pending else decision.status
        statuses.append(status)
        latest = _latest_criterion_results(verification)
        criteria = RequirementCriterion.objects.filter(
            requirement=requirement,
            is_active=True,
            required=True,
        ).order_by("order", "id")

        if criteria.exists():
            for criterion in criteria:
                result = latest.get(criterion.id)
                criterion_status = (
                    "pending"
                    if is_pending
                    else result.status if result else "pending"
                )
                references = []
                if result:
                    references = [
                        _evidence_reference(item.evidence)
                        for item in result.evidence_links.select_related(
                            "evidence",
                        ).all()
                    ]
                evidence_text = ", ".join(references) or "No supporting evidence"
                rows.append(
                    f"| {_safe_markdown_text(criterion.text)} | "
                    f"{criterion_status} | {evidence_text} |"
                )
        else:
            rows.append(
                f"| {_safe_markdown_text(requirement.title)} | {status} | "
                f"{_safe_markdown_text(decision.summary) if decision else 'No decision yet'} |"
            )

    if not statuses:
        status = "unverified"
        rows.append("| No linked requirement | unverified | No requirement evidence found |")
    elif "failed" in statuses:
        status = "failed"
    elif "unverified" in statuses:
        status = "unverified"
    elif "stale" in statuses:
        status = "stale"
    elif "pending" in statuses:
        status = "pending"
    elif "partial" in statuses:
        status = "partial"
    else:
        status = "verified"

    summary = (
        f"Delivery decision: **{status.upper()}**\n\n"
        "| Criterion | Status | Evidence |\n"
        "|---|---|---|\n"
        + "\n".join(rows)
    )
    return status, summary


def _check_conclusion(status):
    if status == "verified":
        return "success"
    if status == "not_applicable":
        return "neutral"
    return "failure"


def _upsert_check(client, pull_request, status, summary):
    repository = pull_request.repository
    existing = client.list_check_runs(
        repository.owner,
        repository.name,
        check_name=CHECK_NAME,
        head_sha=pull_request.head_sha,
    )
    check_runs = existing.get("check_runs", []) if isinstance(existing, dict) else []
    matching = [
        check_run
        for check_run in check_runs
        if check_run.get("name") == CHECK_NAME
        and check_run.get("head_sha") == pull_request.head_sha
        and isinstance(check_run.get("id"), int)
    ]
    payload = {
        "name": CHECK_NAME,
        "head_sha": pull_request.head_sha,
        "status": "in_progress" if status == "pending" else "completed",
        "output": {
            "title": f"Delivery verification: {status}",
            "summary": summary,
        },
    }
    if status == "pending":
        payload["started_at"] = timezone.now().isoformat()
    else:
        payload["completed_at"] = timezone.now().isoformat()
        payload["conclusion"] = _check_conclusion(status)
    if matching:
        latest = max(matching, key=lambda item: item["id"])
        existing_output = latest.get("output") or {}
        if (
            latest.get("status") == payload["status"]
            and latest.get("conclusion") == payload.get("conclusion")
            and existing_output.get("title") == payload["output"]["title"]
            and existing_output.get("summary") == summary
        ):
            return
        update_payload = {
            key: value
            for key, value in payload.items()
            if key not in {"name", "head_sha"}
        }
        if status == "pending":
            update_payload["conclusion"] = None
            update_payload["completed_at"] = None
        client.update_check_run(
            repository.owner,
            repository.name,
            latest["id"],
            update_payload,
        )
    else:
        client.create_check_run(repository.owner, repository.name, payload)


def _upsert_comment(client, pull_request, summary):
    repository = pull_request.repository
    body = f"{COMMENT_MARKER}\n{summary}"
    body_hash = hashlib.sha256(body.encode("utf-8")).hexdigest()
    if pull_request.aci_comment_id:
        if pull_request.aci_comment_hash == body_hash:
            return
        client.update_pull_request_comment(
            repository.owner,
            repository.name,
            pull_request.aci_comment_id,
            body,
        )
        pull_request.aci_comment_hash = body_hash
        pull_request.save(update_fields=["aci_comment_hash"])
        return

    comments = client.list_pull_request_comments(
        repository.owner,
        repository.name,
        pull_request.number,
    )
    comments = comments if isinstance(comments, list) else []
    existing = next(
        (
            comment
            for comment in comments
            if COMMENT_MARKER in comment.get("body", "")
            and isinstance(comment.get("id"), int)
        ),
        None,
    )
    if existing:
        comment_id = existing["id"]
        client.update_pull_request_comment(
            repository.owner,
            repository.name,
            comment_id,
            body,
        )
    else:
        created = client.create_pull_request_comment(
            repository.owner,
            repository.name,
            pull_request.number,
            body,
        )
        comment_id = created.get("id") if isinstance(created, dict) else None
    if not isinstance(comment_id, int):
        raise GitHubAPIError(
            "GitHub did not return the ACI pull request comment ID."
        )
    pull_request.aci_comment_id = comment_id
    pull_request.aci_comment_hash = body_hash
    pull_request.save(update_fields=["aci_comment_id", "aci_comment_hash"])


def publish_delivery_result(pull_request, *, github_client=None):
    """Publish one current Check Run and maintain one comment per pull request."""

    repository = pull_request.repository
    if not repository.github_installation_id and github_client is None:
        raise GitHubAPIError(
            "GitHub App installation is required to publish delivery output."
        )
    github_client = github_client or GitHubClient(
        installation_id=repository.github_installation_id,
    )
    status, summary = build_delivery_report(pull_request)
    _upsert_check(github_client, pull_request, status, summary)
    _upsert_comment(github_client, pull_request, summary)
