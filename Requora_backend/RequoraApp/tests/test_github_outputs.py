from unittest.mock import Mock

import pytest

from Requora_backend.RequoraApp.models import (
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
from Requora_backend.integrations.github.client import GitHubAPIError
from Requora_backend.integrations.github.outputs import (
    CHECK_NAME,
    COMMENT_MARKER,
    build_delivery_report,
    publish_delivery_result,
)


@pytest.fixture
def pull_request():
    repository = Repository.objects.create(
        github_id=98100,
        owner="Requora",
        name="delivery",
        full_name="Requora/delivery",
        github_installation_id=98101,
    )
    pull_request = PullRequest.objects.create(
        repository=repository,
        github_id=98102,
        number=8,
        title="Deliver password reset",
        author="Requora",
        source_branch="feature/reset",
        target_branch="main",
        base_sha="b" * 40,
        head_sha="a" * 40,
        created_at="2026-10-28T07:00:00Z",
        updated_at="2026-10-28T07:00:00Z",
    )
    requirement = Requirement.objects.create(
        repository=repository,
        external_id="Requora-8",
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
        metadata={
            "filename": "tests/test_reset.py",
            "line_start": 10,
            "line_end": 23,
            "source_url": (
                "https://github.com/Requora/delivery/blob/main/"
                "tests/test_reset.py#L10-L23"
            ),
            "snippet": "def send_reset_email():\n    return True",
        },
    )
    CriterionVerificationEvidence.objects.create(
        criterion_verification=criterion_result,
        evidence=evidence,
    )
    return pull_request


@pytest.mark.django_db
def test_delivery_report_includes_primary_snapshot_and_all_evidence_link(
    pull_request,
    settings,
):
    settings.FRONTEND_URL = "https://requora.example/"
    status, summary = build_delivery_report(pull_request)

    assert status == "verified"
    assert "A reset email is sent\\." in summary
    assert (
        "[tests/test\\_reset\\.py:10-23]("
        "https://github.com/Requora/delivery/blob/main/tests/test_reset.py#L10-L23)"
    ) in summary
    assert (
        "<code>def send_reset_email():</code><br>"
        "<code>    return True</code>"
    ) in summary
    assert (
        "[View all 1 evidence item]"
        "(https://requora.example/verifications/"
        f"{pull_request.verifications.get().id}/criteria/"
        f"{pull_request.requirement_links.get().requirement.criteria.get().id}"
        "/evidence)"
    ) in summary


@pytest.mark.django_db
def test_delivery_report_wraps_long_criteria(pull_request):
    criterion = RequirementCriterion.objects.get(text="A reset email is sent.")
    criterion.text = (
        "After repeated failed attempts, reject additional sign-ins temporarily "
        "and allow access again when the configured lockout expires."
    )
    criterion.save(update_fields=["text"])

    _, summary = build_delivery_report(pull_request)

    assert "After repeated failed attempts, reject<br>" in summary
    assert "configured lockout expires\\." in summary


@pytest.mark.django_db
def test_delivery_report_links_other_evidence_instead_of_listing_each_reference(
    pull_request,
    settings,
):
    settings.FRONTEND_URL = "https://requora.example"
    criterion_result = CriterionVerification.objects.get(
        verification__pull_request=pull_request,
    )
    for index in range(2, 7):
        evidence = Evidence.objects.create(
            requirement=criterion_result.criterion.requirement,
            pull_request=pull_request,
            evidence_type="code",
            metadata={
                "filename": f"src/module_{index}.py",
                "line_start": index * 10,
                "line_end": index * 10 + 2,
                "source_url": (
                    "https://github.com/Requora/delivery/blob/main/"
                    f"src/module_{index}.py#L{index * 10}-L{index * 10 + 2}"
                ),
            },
        )
        CriterionVerificationEvidence.objects.create(
            criterion_verification=criterion_result,
            evidence=evidence,
        )

    _, summary = build_delivery_report(pull_request)

    assert "[src/module\\_6\\.py:60-62]" in summary
    for index in (2, 3, 4, 5):
        assert f"[src/module\\_{index}\\.py:" not in summary
    assert "[View all 6 evidence items](" in summary


@pytest.mark.django_db
def test_publish_delivery_result_creates_check_and_persists_single_comment(
    pull_request,
):
    _, expected_summary = build_delivery_report(pull_request)
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
                        "summary": expected_summary,
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
                        "summary": expected_summary,
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
    assert (
        "https://github.com/Requora/delivery/blob/main/tests/test_reset.py#L10-L23"
        in
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


@pytest.mark.django_db
def test_reopening_completed_check_omits_null_completion_fields(pull_request):
    verification = Verification.objects.get(pull_request=pull_request)
    verification.status = "pending"
    verification.save(update_fields=["status"])
    DeliveryDecision.objects.filter(verification=verification).delete()

    github_client = Mock()
    github_client.list_check_runs.return_value = {
        "check_runs": [
            {
                "id": 98106,
                "name": CHECK_NAME,
                "status": "completed",
                "head_sha": pull_request.head_sha,
                "conclusion": "success",
                "output": {
                    "title": "Delivery verification: verified",
                    "summary": "Previous result",
                },
            },
        ],
    }
    github_client.list_pull_request_comments.return_value = [
        {"id": 98107, "body": COMMENT_MARKER},
    ]

    publish_delivery_result(pull_request, github_client=github_client)

    update_payload = github_client.update_check_run.call_args.args[3]
    assert update_payload["status"] == "in_progress"
    assert "conclusion" not in update_payload
    assert "completed_at" not in update_payload


@pytest.mark.django_db
def test_comment_permission_failure_does_not_block_check_publication(
    pull_request,
):
    github_client = Mock()
    github_client.list_check_runs.return_value = {"check_runs": []}
    github_client.list_pull_request_comments.return_value = []
    github_client.create_pull_request_comment.side_effect = GitHubAPIError(
        "GitHub API request failed (403): Resource not accessible by integration"
    )

    publish_delivery_result(pull_request, github_client=github_client)

    github_client.create_check_run.assert_called_once()
    github_client.create_pull_request_comment.assert_called_once()
