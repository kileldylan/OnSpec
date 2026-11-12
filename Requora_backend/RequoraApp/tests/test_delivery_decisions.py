import pytest

from Requora_backend.RequoraApp.models import (
    ChangedFile,
    Commit,
    Evidence,
    PullRequest,
    Repository,
    Requirement,
    Verification,
)
from Requora_backend.integrations.verification.criteria import (
    create_criterion,
    record_criterion_verification,
)
from Requora_backend.integrations.verification.decisions import (
    create_delivery_decision,
)
from Requora_backend.integrations.verification.service import (
    invalidate_evidence_for_changed_file,
)


@pytest.fixture
def verification():
    repository = Repository.objects.create(
        github_id=99100,
        owner="Requora",
        name="decisions",
        full_name="Requora/decisions",
    )
    requirement = Requirement.objects.create(
        repository=repository,
        external_id="Requora-2",
        source="manual",
        title="Reset passwords",
    )
    pull_request = PullRequest.objects.create(
        repository=repository,
        github_id=99101,
        number=1,
        title="Reset passwords",
        author="Requora",
        source_branch="feature/reset",
        target_branch="main",
        base_sha="b" * 40,
        head_sha="a" * 40,
        created_at="2026-08-19T07:00:00Z",
        updated_at="2026-08-19T07:00:00Z",
    )
    return Verification.objects.create(
        requirement=requirement,
        pull_request=pull_request,
        status="verified",
        confidence=0.90,
    )


@pytest.mark.django_db
def test_delivery_decision_reports_missing_required_criteria(verification):
    criterion = create_criterion(
        requirement=verification.requirement,
        text="A reset email is sent.",
        category="integration",
    )

    decision = create_delivery_decision(verification=verification)

    assert decision.status == "unverified"
    assert decision.rationale["missing_required_criteria"] == [
        {"id": criterion.id, "text": criterion.text},
    ]


@pytest.mark.django_db
def test_new_decision_supersedes_prior_snapshot(verification):
    criterion = create_criterion(
        requirement=verification.requirement,
        text="A reset flow exists.",
    )
    first = create_delivery_decision(verification=verification)
    record_criterion_verification(
        verification=verification,
        criterion=criterion,
        status="satisfied",
    )
    second = create_delivery_decision(verification=verification)

    first.refresh_from_db()
    assert first.is_current is False
    assert first.superseded_at is not None
    assert second.is_current is True
    assert second.status == "verified"


@pytest.mark.django_db
def test_evidence_invalidation_marks_current_decision_stale(verification):
    criterion = create_criterion(
        requirement=verification.requirement,
        text="A reset flow exists.",
    )
    commit = Commit.objects.create(
        repository=verification.requirement.repository,
        pull_request=verification.pull_request,
        sha="c" * 40,
        message="Add reset flow",
        author="Requora",
        committed_at="2026-08-19T07:00:00Z",
    )
    original_file = ChangedFile.objects.create(
        commit=commit,
        filename="accounts/reset.py",
        status="modified",
    )
    evidence = Evidence.objects.create(
        requirement=verification.requirement,
        pull_request=verification.pull_request,
        commit=commit,
        changed_file=original_file,
        evidence_type="code",
    )
    record_criterion_verification(
        verification=verification,
        criterion=criterion,
        status="satisfied",
        evidence=[evidence],
    )
    decision = create_delivery_decision(verification=verification)

    newer_commit = Commit.objects.create(
        repository=verification.requirement.repository,
        pull_request=verification.pull_request,
        sha="d" * 40,
        message="Change reset flow",
        author="Requora",
        committed_at="2026-08-19T08:00:00Z",
    )
    newer_file = ChangedFile.objects.create(
        commit=newer_commit,
        filename="accounts/reset.py",
        status="modified",
    )
    invalidate_evidence_for_changed_file(newer_file)

    decision.refresh_from_db()
    assert decision.status == "stale"
    assert decision.invalidated_at is not None
