import pytest

from Requora_backend.RequoraApp.models import (
    PullRequest,
    Repository,
    Requirement,
    Verification,
)
from Requora_backend.integrations.verification.service import (
    create_verification,
)


@pytest.mark.django_db
def test_create_verification_creates_pending_verification():
    repository = Repository.objects.create(
        github_id=123456,
        owner="kilel",
        name="Requora-demo",
        full_name="kilel/Requora-demo",
        default_branch="main",
    )

    pull_request = PullRequest.objects.create(
        repository=repository,
        github_id=987654,
        number=1,
        title="Add authentication",
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
        external_id="PROJ-123",
        source="jira",
        title="Add authentication",
        description="Users must be able to authenticate.",
    )

    verification = create_verification(
        requirement=requirement,
        pull_request=pull_request,
    )

    assert verification.requirement == requirement
    assert verification.pull_request == pull_request
    assert verification.status == "pending"

    assert verification.summary == ""
    assert verification.confidence is None
    assert verification.verified_at is None
    assert verification.invalidated_at is None

    assert Verification.objects.count() == 1


@pytest.mark.django_db
def test_create_verification_is_idempotent():
    repository = Repository.objects.create(
        github_id=123456,
        owner="kilel",
        name="Requora-demo",
        full_name="kilel/Requora-demo",
        default_branch="main",
    )

    pull_request = PullRequest.objects.create(
        repository=repository,
        github_id=987654,
        number=1,
        title="Add authentication",
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
        external_id="PROJ-123",
        source="jira",
        title="Add authentication",
        description="Users must be able to authenticate.",
    )

    first = create_verification(
        requirement=requirement,
        pull_request=pull_request,
    )

    second = create_verification(
        requirement=requirement,
        pull_request=pull_request,
    )

    assert first.id == second.id
    assert Verification.objects.count() == 1


@pytest.mark.django_db
def test_create_verification_does_not_modify_existing_verification():
    repository = Repository.objects.create(
        github_id=123456,
        owner="kilel",
        name="Requora-demo",
        full_name="kilel/Requora-demo",
        default_branch="main",
    )

    pull_request = PullRequest.objects.create(
        repository=repository,
        github_id=987654,
        number=1,
        title="Add authentication",
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
        external_id="PROJ-123",
        source="jira",
        title="Add authentication",
        description="Users must be able to authenticate.",
    )

    existing = Verification.objects.create(
        requirement=requirement,
        pull_request=pull_request,
        status="partial",
        summary="Authentication appears partially implemented.",
        confidence=0.75,
    )

    verification = create_verification(
        requirement=requirement,
        pull_request=pull_request,
    )

    verification.refresh_from_db()

    assert verification.id == existing.id
    assert verification.status == "partial"
    assert verification.summary == (
        "Authentication appears partially implemented."
    )
    assert verification.confidence == 0.75

    assert Verification.objects.count() == 1