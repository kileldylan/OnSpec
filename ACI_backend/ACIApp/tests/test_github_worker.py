from unittest.mock import patch

import pytest
from django.utils import timezone

from ACI_backend.ACIApp.models import (
    ChangedFile,
    Commit,
    PullRequest,
    Repository,
    Requirement,
    RequirementPullRequest,
    Verification,
    VerificationRun,
)
from ACI_backend.integrations.github.service import process_github_webhook
from ACI_backend.integrations.github.worker import (
    enqueue_github_webhook,
    process_next_github_webhook,
    run_worker_iteration,
)
from ACI_backend.integrations.verification.service import claim_reverification_run


def raise_after_claim(*, run_id, **_kwargs):
    claim_reverification_run(run_id=run_id)
    raise RuntimeError("unexpected evaluator failure")


@pytest.mark.django_db
@patch("ACI_backend.integrations.github.service.process_github_webhook")
def test_webhook_worker_claims_and_completes_durable_job(mock_process):
    payload = {"action": "opened"}
    first = enqueue_github_webhook(
        event="pull_request",
        payload=payload,
        delivery_id="delivery-one",
    )
    duplicate = enqueue_github_webhook(
        event="pull_request",
        payload=payload,
        delivery_id="delivery-one",
    )

    assert first.id == duplicate.id
    job = process_next_github_webhook()

    assert job.status == "completed"
    assert job.attempts == 1
    mock_process.assert_called_once_with(
        event="pull_request",
        payload=payload,
    )


@pytest.mark.django_db
@patch(
    "ACI_backend.integrations.github.service.process_github_webhook",
    side_effect=RuntimeError("temporary processing error"),
)
def test_webhook_worker_retries_then_marks_terminal_failure(_mock_process):
    job = enqueue_github_webhook(
        event="pull_request",
        payload={"action": "opened"},
        delivery_id="delivery-fail",
    )

    for attempt in range(5):
        job = process_next_github_webhook()
        job.refresh_from_db()
        assert job.attempts == attempt + 1
        if attempt < 4:
            assert job.status == "queued"
            job.available_at = timezone.now()
            job.save(update_fields=["available_at"])

    assert job.status == "failed"
    assert "temporary processing error" in job.last_error


@pytest.mark.django_db
@patch("ACI_backend.integrations.github.outputs.publish_delivery_result")
def test_completed_ci_check_queues_linked_verification(mock_publish):
    repository = Repository.objects.create(
        github_id=987620,
        owner="aci",
        name="worker-evidence",
        full_name="aci/worker-evidence",
        github_installation_id=987621,
    )
    pull_request = PullRequest.objects.create(
        repository=repository,
        github_id=987622,
        number=22,
        title="Add account tests",
        author="aci",
        source_branch="feature/tests",
        target_branch="main",
        base_sha="b" * 40,
        head_sha="a" * 40,
        created_at="2026-10-28T07:00:00Z",
        updated_at="2026-10-28T07:00:00Z",
    )
    requirement = Requirement.objects.create(
        repository=repository,
        external_id="TEST-22",
        source="manual",
        title="Account behavior",
    )
    RequirementPullRequest.objects.create(
        requirement=requirement,
        pull_request=pull_request,
    )
    commit = Commit.objects.create(
        repository=repository,
        pull_request=pull_request,
        sha=pull_request.head_sha,
        message="Add account tests",
        author="aci",
        committed_at="2026-10-28T07:00:00Z",
    )
    ChangedFile.objects.create(
        commit=commit,
        filename="tests/test_account.py",
        status="added",
        patch="@@ -0,0 +1 @@\n+def test_account():\n",
    )

    evidence = process_github_webhook(
        event="check_run",
        payload={
            "action": "completed",
            "repository": {"id": repository.github_id},
            "check_run": {
                "id": 123,
                "name": "pytest",
                "status": "completed",
                "conclusion": "success",
                "head_sha": pull_request.head_sha,
                "pull_requests": [{"number": pull_request.number}],
            },
        },
    )

    assert evidence
    run = VerificationRun.objects.get(
        verification__requirement=requirement,
        status="queued",
    )
    assert run.triggering_changed_file.filename == "tests/test_account.py"
    mock_publish.assert_called_once_with(pull_request)


@pytest.mark.django_db
@patch("ACI_backend.integrations.github.outputs.publish_delivery_result")
@patch(
    "ACI_backend.integrations.verification.service.process_next_reverification_run",
    side_effect=raise_after_claim,
)
def test_unexpected_verification_error_fails_run_and_publishes(
    _mock_process,
    mock_publish,
):
    repository = Repository.objects.create(
        github_id=987630,
        owner="aci",
        name="worker-failure",
        full_name="aci/worker-failure",
    )
    pull_request = PullRequest.objects.create(
        repository=repository,
        github_id=987631,
        number=23,
        title="Add account tests",
        author="aci",
        source_branch="feature/tests",
        target_branch="main",
        base_sha="b" * 40,
        head_sha="a" * 40,
        created_at="2026-10-28T07:00:00Z",
        updated_at="2026-10-28T07:00:00Z",
    )
    requirement = Requirement.objects.create(
        repository=repository,
        external_id="TEST-23",
        source="manual",
        title="Account behavior",
    )
    verification = Verification.objects.create(
        requirement=requirement,
        pull_request=pull_request,
    )
    commit = Commit.objects.create(
        repository=repository,
        pull_request=pull_request,
        sha=pull_request.head_sha,
        message="Add account tests",
        author="aci",
        committed_at="2026-10-28T07:00:00Z",
    )
    changed_file = ChangedFile.objects.create(
        commit=commit,
        filename="tests/test_account.py",
        status="added",
    )
    run = VerificationRun.objects.create(
        verification=verification,
        triggering_changed_file=changed_file,
        reason="CI evidence changed",
    )

    assert run_worker_iteration()

    run.refresh_from_db()
    verification.refresh_from_db()
    assert run.status == "failed"
    assert verification.status == "failed"
    mock_publish.assert_called_once_with(pull_request)
