import logging
import time
import uuid
from datetime import timedelta

from django.db import transaction
from django.utils import timezone

from ACI_backend.ACIApp.models import GitHubWebhookJob


logger = logging.getLogger(__name__)
MAX_WEBHOOK_ATTEMPTS = 5


def enqueue_github_webhook(*, event, payload, delivery_id=None):
    """Persist a webhook for background processing; duplicate deliveries are safe."""

    job, _ = GitHubWebhookJob.objects.get_or_create(
        delivery_id=delivery_id or str(uuid.uuid4()),
        defaults={
            "event": event,
            "payload": payload,
            "available_at": timezone.now(),
        },
    )
    return job


@transaction.atomic
def _claim_next_job():
    job = (
        GitHubWebhookJob.objects.select_for_update(skip_locked=True)
        .filter(status="queued", available_at__lte=timezone.now())
        .order_by("received_at", "id")
        .first()
    )
    if job is None:
        return None
    job.status = "running"
    job.attempts += 1
    job.started_at = timezone.now()
    job.save(update_fields=["status", "attempts", "started_at"])
    return job


def process_next_github_webhook():
    """Process one durable webhook job without propagating errors to HTTP."""

    job = _claim_next_job()
    if job is None:
        return None

    try:
        from ACI_backend.integrations.github.service import (
            process_github_webhook,
        )

        process_github_webhook(event=job.event, payload=job.payload)
    except Exception as error:
        logger.exception(
            "GitHub webhook job %s (%s) failed on attempt %s.",
            job.delivery_id,
            job.event,
            job.attempts,
        )
        delay_seconds = min(2 ** job.attempts, 60)
        job.status = (
            "failed" if job.attempts >= MAX_WEBHOOK_ATTEMPTS else "queued"
        )
        job.last_error = str(error)[:4000]
        job.available_at = timezone.now() + timedelta(seconds=delay_seconds)
        job.completed_at = timezone.now() if job.status == "failed" else None
        job.save(
            update_fields=[
                "status",
                "last_error",
                "available_at",
                "completed_at",
            ],
        )
        return job

    job.status = "completed"
    job.last_error = ""
    job.completed_at = timezone.now()
    job.save(update_fields=["status", "last_error", "completed_at"])
    return job


def recover_stuck_github_webhooks(*, timeout=timedelta(minutes=10)):
    """Requeue jobs left running after a worker process stopped."""

    cutoff = timezone.now() - timeout
    stuck_jobs = GitHubWebhookJob.objects.filter(
        status="running",
        started_at__lt=cutoff,
    )
    return stuck_jobs.update(
        status="queued",
        available_at=timezone.now(),
        last_error="Recovered after worker stopped before completing the job.",
    )


def _publish_failed_verification(run_id):
    from ACI_backend.ACIApp.models import VerificationRun
    from ACI_backend.integrations.github.outputs import publish_delivery_result
    from ACI_backend.integrations.verification.decisions import (
        create_delivery_decision,
    )

    run = VerificationRun.objects.select_related(
        "verification__pull_request__repository",
    ).get(pk=run_id)
    create_delivery_decision(verification=run.verification)
    if (
        run.verification.pull_request_id
        and run.verification.pull_request.repository.github_installation_id
    ):
        publish_delivery_result(run.verification.pull_request)
    elif run.verification.pull_request_id:
        logger.warning(
            "Failed verification was saved, but its GitHub result was not "
            "published because no installation is linked to %s.",
            run.verification.pull_request,
        )


def _fail_running_verification(run_id):
    from ACI_backend.ACIApp.models import VerificationRun
    from ACI_backend.integrations.verification.service import (
        complete_reverification_run,
    )

    run = VerificationRun.objects.get(pk=run_id)
    if run.status != "running":
        return False
    complete_reverification_run(
        run_id=run.id,
        status="failed",
        summary="Verification worker failed. See backend logs.",
        confidence=0.0,
    )
    try:
        _publish_failed_verification(run.id)
    except Exception:
        logger.exception(
            "Verification run %s failed and was saved, but its GitHub result "
            "could not be published.",
            run.id,
        )
    return True


def run_worker_iteration(*, evaluator=None, test_runner=None):
    """Handle a webhook and a verification run, if either is ready."""

    webhook_job = process_next_github_webhook()
    verification_run_id = None
    verification_failed = False
    try:
        from ACI_backend.ACIApp.models import VerificationRun
        from ACI_backend.integrations.verification.service import (
            collect_repository_code_evidence,
            process_next_reverification_run,
        )
        from ACI_backend.integrations.verification.errors import (
            VerificationProcessingError,
        )
        verification_run_id = (
            VerificationRun.objects.filter(status="queued")
            .order_by("requested_at")
            .values_list("id", flat=True)
            .first()
        )
        verification = process_next_reverification_run(
            evaluator=evaluator,
            test_runner=test_runner,
            source_evidence_collector=collect_repository_code_evidence,
            run_id=verification_run_id,
        )
    except VerificationProcessingError as error:
        logger.error("%s", error)
        verification_failed = True
        try:
            _publish_failed_verification(error.run_id)
        except Exception:
            logger.exception(
                "Unable to publish failed verification run %s.",
                error.run_id,
            )
        verification = None
    except Exception:
        logger.exception("ACI verification worker failed.")
        if verification_run_id is not None:
            try:
                verification_failed = _fail_running_verification(
                    verification_run_id,
                )
            except Exception:
                logger.exception(
                    "Unable to mark verification run %s failed.",
                    verification_run_id,
                )
        verification = None
    return (
        webhook_job is not None
        or verification is not None
        or verification_failed
    )


def run_worker(*, poll_interval=5, once=False, evaluator=None, test_runner=None):
    """Poll the database-backed queues until stopped or one iteration ends."""

    while True:
        recover_stuck_github_webhooks()
        from ACI_backend.integrations.verification.service import (
            recover_stuck_reverification_runs,
        )

        recover_stuck_reverification_runs()
        processed = run_worker_iteration(
            evaluator=evaluator,
            test_runner=test_runner,
        )
        if once:
            return
        if not processed:
            time.sleep(poll_interval)
