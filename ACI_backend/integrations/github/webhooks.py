import json
import hashlib
import hmac
import logging

from django.conf import settings
from django.http import JsonResponse
from django.views.decorators.csrf import csrf_exempt

from ACI_backend.integrations.github.client import GitHubAPIError
from ACI_backend.integrations.github.service import (
    process_github_installation_event,
    process_github_evidence_event,
    process_pull_request_event,
)

logger = logging.getLogger(__name__)

PULL_REQUEST_ACTIONS = {"opened", "reopened", "synchronize", "closed"}
INSTALLATION_ACTIONS = {"created", "deleted"}
INSTALLATION_REPOSITORIES_ACTIONS = {"added", "removed"}
CHECK_RUN_ACTIONS = {"created", "rerequested", "completed"}


@csrf_exempt
def github_webhook(request):
    """Django view that receives GitHub webhooks and dispatches processing.

    Verifies the `X-Hub-Signature-256` header using
    `settings.GITHUB_WEBHOOK_SECRET` and returns 401 on failure.
    """
    if request.method != "POST":
        return JsonResponse({"detail": "Method not allowed."}, status=405)

    signature = request.headers.get("X-Hub-Signature-256")
    if not signature or not signature.startswith("sha256="):
        return JsonResponse({"detail": "Invalid webhook signature."}, status=401)

    webhook_secret = getattr(settings, "GITHUB_WEBHOOK_SECRET", "")
    if not webhook_secret:
        return JsonResponse(
            {"detail": "Webhook secret is not configured."},
            status=503,
        )
    expected = "sha256=" + hmac.new(
        webhook_secret.encode(), request.body, hashlib.sha256
    ).hexdigest()

    if not hmac.compare_digest(signature, expected):
        return JsonResponse({"detail": "Invalid webhook signature."}, status=401)

    try:
        payload = json.loads(request.body)
    except json.JSONDecodeError:
        return JsonResponse({"detail": "Invalid JSON payload."}, status=400)

    event = request.headers.get("X-GitHub-Event")
    if not isinstance(payload, dict) or not event:
        return JsonResponse({"detail": "Invalid webhook payload."}, status=400)

    try:
        if event == "pull_request":
            if not isinstance(payload.get("repository"), dict):
                return JsonResponse({"detail": "Invalid pull request payload."}, status=400)
            if not isinstance(payload.get("pull_request"), dict):
                return JsonResponse({"detail": "Invalid pull request payload."}, status=400)
            if payload.get("action") not in PULL_REQUEST_ACTIONS:
                return JsonResponse(
                    {"message": "Webhook action ignored.", "event": event},
                    status=202,
                )
            pull_request = process_pull_request_event(payload)
            requirements = list(
                pull_request.requirement_links.select_related(
                    "requirement",
                ).values(
                    "requirement_id",
                    "requirement__external_id",
                    "requirement__title",
                )
            )
            verifications = list(
                pull_request.verifications.values(
                    "id",
                    "requirement_id",
                    "status",
                )
            )
            runs = list(
                pull_request.verifications.values(
                    "runs__id",
                    "runs__status",
                )
                .exclude(runs__id__isnull=True)
            )
            return JsonResponse(
                {
                    "message": "Webhook received.",
                    "event": event,
                    "pull_request": {
                        "id": pull_request.id,
                        "number": pull_request.number,
                        "repository": pull_request.repository.full_name,
                    },
                    "requirements": requirements,
                    "verifications": verifications,
                    "runs": runs,
                    "analysis": (
                        "queued; run process_reverification_runs to complete"
                        if any(item["runs__status"] == "queued" for item in runs)
                        else "not queued; link a Jira requirement and ensure the PR has changed files"
                    ),
                },
                status=200,
            )
        elif event == "installation":
            if not isinstance(payload.get("installation"), dict):
                return JsonResponse(
                    {"detail": "Invalid installation payload."},
                    status=400,
                )
            if payload.get("action") not in INSTALLATION_ACTIONS:
                return JsonResponse(
                    {"message": "Webhook action ignored.", "event": event},
                    status=202,
                )
            process_github_installation_event(event, payload)
        elif event == "installation_repositories":
            if not isinstance(payload.get("installation"), dict):
                return JsonResponse(
                    {"detail": "Invalid installation payload."},
                    status=400,
                )
            if payload.get("action") not in INSTALLATION_REPOSITORIES_ACTIONS:
                return JsonResponse(
                    {"message": "Webhook action ignored.", "event": event},
                    status=202,
                )
            process_github_installation_event(event, payload)
        elif event == "check_run":
            if not isinstance(payload.get("repository"), dict):
                return JsonResponse({"detail": "Invalid check run payload."}, status=400)
            if payload.get("action") not in CHECK_RUN_ACTIONS:
                return JsonResponse(
                    {"message": "Webhook action ignored.", "event": event},
                    status=202,
                )
            process_github_evidence_event(event, payload)
        elif event == "status":
            if not isinstance(payload.get("repository"), dict):
                return JsonResponse({"detail": "Invalid status payload."}, status=400)
            process_github_evidence_event(event, payload)
        else:
            return JsonResponse(
                {"message": "Webhook event ignored.", "event": event},
                status=202,
            )
    except GitHubAPIError:
        logger.exception("GitHub API request failed while processing webhook.")
        return JsonResponse(
            {"detail": "GitHub API request failed."},
            status=502,
        )
    except (KeyError, TypeError, ValueError):
        return JsonResponse({"detail": "Invalid webhook payload."}, status=400)

    return JsonResponse({"message": "Webhook received.", "event": event}, status=200)