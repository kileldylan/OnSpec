from unittest.mock import Mock

import pytest

from ACI_backend.ACIApp.models import (
    CriterionVerification,
    CriterionVerificationEvidence,
    DeliveryDecision,
    Evidence,
    PullRequest,
    Repository,
    Requirement,
    RequirementCriterion,
    RequirementPullRequest,
    Verification,
)
from ACI_backend.integrations.github.outputs import (
    CHECK_NAME,
    COMMENT_MARKER,
    build_delivery_report,
    publish_delivery_result,
)


@pytest.fixture
def pull_request():
    repository = Repository.objects.create(
        github_id=98100,
        owner="aci",
        name="delivery",
        full_name="aci/delivery",
        github_installation_id=98101,
    )
    pull_request = PullRequest.objects.create(
        repository=repository,
        github_id=98102,
        number=8,
        title="Deliver password reset",
        author="aci",
        source_branch="feature/reset",
        target_branch="main",
        base_sha="b" * 40,
        head_sha="a" * 40,
        created_at="2026-10-28T07:00:00Z",
        updated_at="2026-10-28T07:00:00Z",
    )
    requirement = Requirement.objects.create(
        repository=repository,
        external_id="ACI-8",
        source="manual",
        title="Password reset",
    )
    RequirementPullRequest.objects.create(
        requirement=requirement,
        pull_request=pull_request,
    )
    verification = Verification.objects.create(
        requirement=requirement,
        pull_request=pull_request,
        status="verified",
    )
    decision = DeliveryDecision.objects.create(
        verification=verification,
        status="verified",
        summary="All required criteria are satisfied.",
    )
    criterion = RequirementCriterion.objects.create(
        requirement=requirement,
        text="A reset email is sent.",
    )
    criterion_result = CriterionVerification.objects.create(
        verification=verification,
        criterion=criterion,
        status="satisfied",
    )
    evidence = Evidence.objects.create(
        requirement=requirement,
        pull_request=pull_request,
        evidence_type="test",
        description="Reset email behavior is covered by a test.",
        metadata={"source_url": "https://github.com/aci/delivery/blob/main/tests/test_reset.py"},
    )
    CriterionVerificationEvidence.objects.create(
        criterion_verification=criterion_result,
        evidence=evidence,
    )
    return pull_request


@pytest.mark.django_db
def test_delivery_report_is_evidence_first(pull_request):
    status, summary = build_delivery_report(pull_request)

    assert status == "verified"
    assert "A reset email is sent\\." in summary
    assert "[valid evidence](https://github.com/aci/delivery/blob/main/tests/test_reset.py)" in summary


@pytest.mark.django_db
def test_publish_delivery_result_creates_check_and_persists_single_comment(
    pull_request,
):
    github_client = Mock()
    github_client.list_check_runs.side_effect = [
        {"check_runs": []},
        {
            "check_runs": [
                {
                    "id": 98104,
                    "name": CHECK_NAME,
                    "status": "completed",
                    "head_sha": pull_request.head_sha,
                    "conclusion": "success",
                    "output": {
                        "title": "Delivery verification: verified",
                        "summary": (
                            "Delivery decision: **VERIFIED**\n\n"
                            "| Criterion | Status | Evidence |\n"
                            "|---|---|---|\n"
                            "| A reset email is sent\\. | satisfied | "
                            "[valid evidence](https://github.com/aci/delivery/"
                            "blob/main/tests/test_reset.py) |"
                        ),
                    },
                },
            ],
        },
        {
            "check_runs": [
                {
                    "id": 98104,
                    "name": CHECK_NAME,
                    "status": "completed",
                    "head_sha": pull_request.head_sha,
                    "conclusion": "success",
                    "output": {
                        "title": "Delivery verification: verified",
                        "summary": (
                            "Delivery decision: **VERIFIED**\n\n"
                            "| Criterion | Status | Evidence |\n"
                            "|---|---|---|\n"
                            "| A reset email is sent\\. | satisfied | "
                            "[valid evidence](https://github.com/aci/delivery/"
                            "blob/main/tests/test_reset.py) |"
                        ),
                    },
                },
            ],
        },
    ]
    github_client.list_pull_request_comments.return_value = []
    github_client.create_pull_request_comment.return_value = {"id": 98103}

    publish_delivery_result(pull_request, github_client=github_client)

    check_payload = github_client.create_check_run.call_args.args[2]
    assert check_payload["name"] == CHECK_NAME
    assert check_payload["head_sha"] == pull_request.head_sha
    assert check_payload["conclusion"] == "success"
    assert "https://github.com/aci/delivery/blob/main/tests/test_reset.py" in (
        check_payload["output"]["summary"]
    )

    comment_body = github_client.create_pull_request_comment.call_args.args[3]
    assert comment_body.startswith(COMMENT_MARKER)
    pull_request.refresh_from_db()
    assert pull_request.aci_comment_id == 98103
    assert pull_request.aci_comment_hash

    publish_delivery_result(pull_request, github_client=github_client)
    github_client.create_pull_request_comment.assert_called_once()
    github_client.update_pull_request_comment.assert_not_called()
    github_client.create_check_run.assert_called_once()
    github_client.update_check_run.assert_not_called()

    original_comment_hash = pull_request.aci_comment_hash
    decision = DeliveryDecision.objects.get(
        verification__pull_request=pull_request,
        is_current=True,
    )
    decision.status = "partial"
    decision.save(update_fields=["status"])

    publish_delivery_result(pull_request, github_client=github_client)

    github_client.update_check_run.assert_called_once()
    assert github_client.update_check_run.call_args.args[3]["conclusion"] == (
        "failure"
    )
    github_client.update_pull_request_comment.assert_called_once()
    pull_request.refresh_from_db()
    assert pull_request.aci_comment_hash != original_comment_hash

    assert DeliveryDecision.objects.filter(
        verification__pull_request=pull_request,
        is_current=True,
    ).count() == 1


@pytest.mark.django_db
def test_pending_delivery_keeps_check_run_in_progress(pull_request):
    verification = Verification.objects.get(pull_request=pull_request)
    verification.status = "pending"
    verification.save(update_fields=["status"])
    DeliveryDecision.objects.filter(verification=verification).delete()
    github_client = Mock()
    github_client.list_check_runs.return_value = {"check_runs": []}
    github_client.list_pull_request_comments.return_value = []
    github_client.create_pull_request_comment.return_value = {"id": 98105}

    publish_delivery_result(pull_request, github_client=github_client)

    check_payload = github_client.create_check_run.call_args.args[2]
    assert check_payload["status"] == "in_progress"
    assert "conclusion" not in check_payload
    assert "| pending |" in check_payload["output"]["summary"]
