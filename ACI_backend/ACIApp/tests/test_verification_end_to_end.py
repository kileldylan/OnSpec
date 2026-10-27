from unittest.mock import patch

import pytest

from ACI_backend.ACIApp.models import (
    DeliveryDecision,
    Evidence,
    PullRequest,
    Repository,
    Requirement,
    RequirementPullRequest,
    Verification,
    VerificationEvidence,
)
from ACI_backend.integrations.github.service import (
    process_github_evidence_event,
    process_pull_request_event,
)
from ACI_backend.integrations.verification.decisions import (
    create_delivery_decision,
)
from ACI_backend.integrations.verification.service import (
    ingest_changed_file_evidence,
    process_next_reverification_run,
)


def github_pull_request_payload(*, head_sha):
    return {
        "repository": {
            "id": 654321,
            "name": "aci-e2e",
            "full_name": "kilel/aci-e2e",
            "default_branch": "main",
            "owner": {"login": "kilel"},
        },
        "pull_request": {
            "id": 123321,
            "number": 7,
            "title": "Implement authentication",
            "state": "open",
            "merged": False,
            "created_at": "2026-08-19T10:00:00Z",
            "updated_at": "2026-08-19T10:00:00Z",
            "user": {"login": "kilel"},
            "head": {"ref": "feature/auth", "sha": head_sha},
            "base": {"ref": "main", "sha": "b" * 40},
        },
    }


def github_commit(sha):
    return {
        "sha": sha,
        "commit": {
            "message": "Implement authentication",
            "author": {
                "name": "kilel",
                "date": "2026-08-19T10:30:00Z",
            },
        },
    }


def github_commit_details():
    return {
        "files": [
            {
                "filename": "auth/service.py",
                "status": "modified",
                "additions": 10,
                "deletions": 2,
                "changes": 12,
                "patch": (
                    "@@ -1,3 +1,5 @@\n"
                    "+def authenticate_user(credentials):\n"
                    "+    return authentication_service.authenticate(credentials)"
                ),
            },
        ],
    }


@pytest.mark.django_db
@patch("ACI_backend.integrations.github.service.GitHubClient")
def test_existing_pipeline_builds_and_refreshes_traceable_decision(
    mock_github_client,
):
    first_sha = "a" * 40
    second_sha = "d" * 40
    mock_github_client.return_value.get_pull_request_commits.side_effect = [
        [github_commit(first_sha)],
        [github_commit(second_sha)],
    ]
    mock_github_client.return_value.get_commit.side_effect = [
        github_commit_details(),
        github_commit_details(),
    ]

    repository = Repository.objects.create(
        github_id=654321,
        owner="kilel",
        name="aci-e2e",
        full_name="kilel/aci-e2e",
    )
    requirement = Requirement.objects.create(
        repository=repository,
        external_id="AUTH-E2E",
        source="jira",
        title="Users can authenticate",
    )

    process_pull_request_event(github_pull_request_payload(head_sha=first_sha))
    pull_request = PullRequest.objects.get(repository=repository, number=7)
    RequirementPullRequest.objects.create(
        requirement=requirement,
        pull_request=pull_request,
    )
    ingest_changed_file_evidence(requirement, pull_request)

    process_github_evidence_event(
        "check_run",
        {
            "repository": {"id": repository.github_id},
            "check_run": {
                "id": 1,
                "name": "pytest",
                "status": "completed",
                "conclusion": "success",
                "head_sha": first_sha,
                "pull_requests": [{"number": pull_request.number}],
            },
        },
    )
    process_github_evidence_event(
        "status",
        {
            "repository": {"id": repository.github_id},
            "sha": first_sha,
            "context": "build",
            "state": "success",
        },
    )

    verification = Verification.objects.create(
        requirement=requirement,
        pull_request=pull_request,
        status="verified",
        summary="All deterministic evidence is present.",
        confidence=0.9,
    )
    first_evidence = Evidence.objects.filter(
        requirement=requirement,
        pull_request=pull_request,
        status="valid",
    )
    VerificationEvidence.objects.bulk_create(
        [
            VerificationEvidence(verification=verification, evidence=item)
            for item in first_evidence
        ]
    )
    first_decision = create_delivery_decision(verification=verification)

    process_pull_request_event(github_pull_request_payload(head_sha=second_sha))
    process_github_evidence_event(
        "check_run",
        {
            "repository": {"id": repository.github_id},
            "check_run": {
                "id": 2,
                "name": "pytest",
                "status": "completed",
                "conclusion": "success",
                "head_sha": second_sha,
                "pull_requests": [{"number": pull_request.number}],
            },
        },
    )
    process_github_evidence_event(
        "status",
        {
            "repository": {"id": repository.github_id},
            "sha": second_sha,
            "context": "build",
            "state": "success",
        },
    )

    verification.refresh_from_db()
    assert verification.status == "stale"
    first_decision.refresh_from_db()
    assert first_decision.status == "stale"
    assert verification.runs.filter(status="queued").count() == 1

    refreshed = process_next_reverification_run()

    assert refreshed == verification
    verification.refresh_from_db()
    assert verification.status == "verified"
    assert verification.decisions.filter(is_current=True).count() == 1
    assert verification.decisions.get(is_current=True).status == "verified"
    assert verification.evidence_links.filter(
        evidence__commit__sha=second_sha,
        evidence__status="valid",
    ).count() == 3

    second_decision = create_delivery_decision(verification=verification)
    first_decision.refresh_from_db()
    assert second_decision.status == "verified"
    assert first_decision.is_current is False
    assert DeliveryDecision.objects.filter(
        verification=verification,
        is_current=True,
    ).count() == 1


@pytest.mark.django_db
def test_github_evidence_event_is_safe_before_repository_ingestion():
    from ACI_backend.integrations.github.service import (
        process_github_evidence_event,
    )

    result = process_github_evidence_event(
        "status",
        {
            "repository": {"id": 999999},
            "sha": "a" * 40,
            "context": "build",
            "state": "success",
        },
    )

    assert result == []