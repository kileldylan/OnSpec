import hashlib
import hmac
import json
import logging

from django.conf import settings
from django.http import JsonResponse
from django.views.decorators.csrf import csrf_exempt

from ACI_backend.integrations.github.worker import enqueue_github_webhook


logger = logging.getLogger(__name__)

PULL_REQUEST_ACTIONS = {"opened", "reopened", "synchronize", "closed"}
INSTALLATION_ACTIONS = {"created", "deleted", "new_permissions_accepted"}
INSTALLATION_REPOSITORIES_ACTIONS = {"added", "removed"}
CHECK_RUN_ACTIONS = {"created", "rerequested", "completed"}


@csrf_exempt
def github_webhook(request):
    """Verify and durably queue supported GitHub webhook events."""

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

    if event == "pull_request":
        if not isinstance(payload.get("repository"), dict) or not isinstance(
            payload.get("pull_request"), dict
        ):
            return JsonResponse({"detail": "Invalid pull request payload."}, status=400)
        if payload.get("action") not in PULL_REQUEST_ACTIONS:
            return _ignored(event)
    elif event == "installation":
        if not isinstance(payload.get("installation"), dict):
            return JsonResponse({"detail": "Invalid installation payload."}, status=400)
        if payload.get("action") not in INSTALLATION_ACTIONS:
            return _ignored(event)
    elif event == "installation_repositories":
        if not isinstance(payload.get("installation"), dict):
            return JsonResponse({"detail": "Invalid installation payload."}, status=400)
        if payload.get("action") not in INSTALLATION_REPOSITORIES_ACTIONS:
            return _ignored(event)
    elif event == "check_run":
        check_run = payload.get("check_run")
        if not isinstance(payload.get("repository"), dict) or not isinstance(
            check_run, dict
        ):
            return JsonResponse({"detail": "Invalid check run payload."}, status=400)
        if check_run.get("name") == "ACI / Delivery Verification":
            return JsonResponse(
                {"message": "ACI check run ignored.", "event": event},
                status=202,
            )
        if payload.get("action") not in CHECK_RUN_ACTIONS:
            return _ignored(event)
    elif event == "status":
        if not isinstance(payload.get("repository"), dict):
            return JsonResponse({"detail": "Invalid status payload."}, status=400)
    else:
        return _ignored(event)

    try:
        job = enqueue_github_webhook(
            event=event,
            payload=payload,
            delivery_id=request.headers.get("X-GitHub-Delivery"),
        )
    except Exception:
        logger.exception("Unable to enqueue GitHub %s webhook.", event)
        return JsonResponse(
            {"detail": "Webhook could not be queued; GitHub may retry delivery."},
            status=503,
        )

    return JsonResponse(
        {
            "message": "Webhook queued for background processing.",
            "event": event,
            "job_id": job.id,
        },
        status=202,
    )


def _ignored(event):
    return JsonResponse(
        {"message": "Webhook event ignored.", "event": event},
        status=202,
    )
