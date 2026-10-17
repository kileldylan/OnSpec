import pytest

from ACI_backend.ACIApp.models import (
    Evidence,
    PullRequest,
    Repository,
    Requirement,
    VerificationEvidence,
)
from ACI_backend.ACIApp.services.verification import (
    create_verification,
)
from ACI_backend.integrations.verification.service import (
    classify_github_context,
    validate_evaluator_conclusion,
)


def test_github_context_classification_is_explicit():
    assert classify_github_context("pytest") == "test"
    assert classify_github_context("build") == "ci"
    assert classify_github_context("unrecognized-check") is None


def test_evaluator_contract_accepts_valid_conclusion():
    requirement = Requirement(pk=1)
    pull_request = PullRequest(pk=2)
    evidence = Evidence(
        pk=3,
        requirement=requirement,
        pull_request=pull_request,
        status="valid",
    )
    conclusion = {
        "status": "verified",
        "summary": "Evidence is complete.",
        "confidence": 0.9,
        "evidence": [evidence],
    }

    assert validate_evaluator_conclusion(
        requirement=requirement,
        evidence=[evidence],
        conclusion=conclusion,
    ) == conclusion


def test_evaluator_contract_rejects_stale_evidence():
    requirement = Requirement(pk=1)
    evidence = Evidence(pk=3, requirement=requirement, status="stale")
    conclusion = {
        "status": "verified",
        "summary": "Evidence is complete.",
        "confidence": 0.9,
        "evidence": [evidence],
    }

    with pytest.raises(ValueError, match="stale"):
        validate_evaluator_conclusion(
            requirement=requirement,
            evidence=[evidence],
            conclusion=conclusion,
        )


@pytest.mark.django_db
def test_evaluator_contract_accepts_queryset_evidence():
    repository = Repository.objects.create(
        github_id=654321,
        owner="acme",
        name="aci-demo-qs",
        full_name="acme/aci-demo-qs",
        default_branch="main",
    )
    pull_request = PullRequest.objects.create(
        repository=repository,
        github_id=777,
        number=42,
        title="Fix worker evidence",
        author="dev",
        source_branch="feature/fix",
        target_branch="main",
        base_sha="b" * 40,
        head_sha="a" * 40,
        state="open",
        is_merged=False,
        created_at="2026-08-17T10:00:00Z",
        updated_at="2026-08-17T10:00:00Z",
    )
    requirement = Requirement.objects.create(
        repository=repository,
        external_id="JIRA-QS",
        source="jira",
        title="Worker can verify queryset evidence",
        description="It should accept evidence batches from a queryset.",
    )
    evidence = Evidence.objects.create(
        requirement=requirement,
        pull_request=pull_request,
        evidence_type="code",
        status="valid",
        description="Fresh code from the queued run.",
    )

    conclusion = {
        "status": "verified",
        "summary": "Verified from queryset evidence.",
        "confidence": 0.91,
        "evidence": Evidence.objects.filter(pk=evidence.pk),
    }

    assert validate_evaluator_conclusion(
        requirement=requirement,
        evidence=Evidence.objects.filter(pk=evidence.pk),
        conclusion=conclusion,
    ) == conclusion


@pytest.mark.django_db
def test_create_verification_creates_verification():
    repository = Repository.objects.create(
        github_id=123456,
        owner="kilel",
        name="aci-demo",
        full_name="kilel/aci-demo",
        default_branch="main",
    )

    pull_request = PullRequest.objects.create(
        repository=repository,
        github_id=987654,
        number=1,
        title="Implement authentication",
        author="kilel",
        source_branch="feature/auth",
        target_branch="main",
        base_sha="b" * 40,
        head_sha="a" * 40,
        state="open",
        is_merged=False,
        created_at="2026-08-17T10:00:00Z",
        updated_at="2026-08-17T10:00:00Z",
    )

    requirement = Requirement.objects.create(
        repository=repository,
        external_id="JIRA-104",
        source="jira",
        title="Authentication",
        description=(
            "Users must be able to authenticate."
        ),
    )

    evidence = Evidence.objects.create(
        requirement=requirement,
        pull_request=pull_request,
        evidence_type="code",
        status="valid",
        description="Authentication logic exists.",
    )

    verification = create_verification(
        requirement=requirement,
        pull_request=pull_request,
        status="verified",
        summary="Authentication is implemented.",
        confidence=0.95,
        evidence=[evidence],
    )

    assert verification.pk is not None

    assert verification.requirement == requirement
    assert verification.pull_request == pull_request

    assert verification.status == "verified"
    assert verification.summary == (
        "Authentication is implemented."
    )

    assert verification.confidence == 0.95

    assert verification.evidence_links.count() == 1

    link = verification.evidence_links.first()

    assert link.evidence == evidence

@pytest.mark.django_db
def test_create_verification_supports_multiple_evidence_items():
    repository = Repository.objects.create(
        github_id=123456,
        owner="kilel",
        name="aci-demo",
        full_name="kilel/aci-demo",
        default_branch="main",
    )

    pull_request = PullRequest.objects.create(
        repository=repository,
        github_id=987654,
        number=1,
        title="Implement password reset",
        author="kilel",
        source_branch="feature/password-reset",
        target_branch="main",
        base_sha="b" * 40,
        head_sha="a" * 40,
        state="open",
        is_merged=False,
        created_at="2026-08-17T10:00:00Z",
        updated_at="2026-08-17T10:00:00Z",
    )

    requirement = Requirement.objects.create(
        repository=repository,
        external_id="JIRA-200",
        source="jira",
        title="Password reset",
        description=(
            "Users can reset their password "
            "and receive an email."
        ),
    )

    code_evidence = Evidence.objects.create(
        requirement=requirement,
        pull_request=pull_request,
        evidence_type="code",
        status="valid",
        description="Password reset endpoint exists.",
    )

    test_evidence = Evidence.objects.create(
        requirement=requirement,
        pull_request=pull_request,
        evidence_type="test",
        status="valid",
        description="Password reset is covered by tests.",
    )

    verification = create_verification(
        requirement=requirement,
        pull_request=pull_request,
        status="verified",
        summary="Password reset is implemented and tested.",
        confidence=0.92,
        evidence=[
            code_evidence,
            test_evidence,
        ],
    )

    assert verification.evidence_links.count() == 2

    evidence_ids = set(
        verification.evidence_links.values_list(
            "evidence_id",
            flat=True,
        )
    )

    assert evidence_ids == {
        code_evidence.id,
        test_evidence.id,
    }

@pytest.mark.django_db
def test_create_verification_rejects_invalid_status():
    repository = Repository.objects.create(
        github_id=123456,
        owner="kilel",
        name="aci-demo",
        full_name="kilel/aci-demo",
        default_branch="main",
    )

    pull_request = PullRequest.objects.create(
        repository=repository,
        github_id=987654,
        number=1,
        title="Test PR",
        author="kilel",
        source_branch="feature/test",
        target_branch="main",
        base_sha="b" * 40,
        head_sha="a" * 40,
        state="open",
        is_merged=False,
        created_at="2026-08-17T10:00:00Z",
        updated_at="2026-08-17T10:00:00Z",
    )

    requirement = Requirement.objects.create(
        repository=repository,
        external_id="JIRA-300",
        source="jira",
        title="Test requirement",
    )

    with pytest.raises(ValueError):
        create_verification(
            requirement=requirement,
            pull_request=pull_request,
            status="definitely_not_valid",
        )

@pytest.mark.django_db
def test_create_verification_rejects_invalid_confidence():
    repository = Repository.objects.create(
        github_id=123456,
        owner="kilel",
        name="aci-demo",
        full_name="kilel/aci-demo",
        default_branch="main",
    )

    pull_request = PullRequest.objects.create(
        repository=repository,
        github_id=987654,
        number=1,
        title="Test PR",
        author="kilel",
        source_branch="feature/test",
        target_branch="main",
        base_sha="b" * 40,
        head_sha="a" * 40,
        state="open",
        is_merged=False,
        created_at="2026-08-17T10:00:00Z",
        updated_at="2026-08-17T10:00:00Z",
    )

    requirement = Requirement.objects.create(
        repository=repository,
        external_id="JIRA-301",
        source="jira",
        title="Test requirement",
    )

    with pytest.raises(ValueError):
        create_verification(
            requirement=requirement,
            pull_request=pull_request,
            status="verified",
            confidence=1.5,
        )