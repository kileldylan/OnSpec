import pytest

from Requora_backend.RequoraApp.models import (
    ChangedFile,
    Commit,
    Evidence,
    PullRequest,
    Repository,
    Requirement,
    RequirementPullRequest,
    Verification,
    VerificationEvidence,
)


@pytest.mark.django_db
def test_requirement_can_be_linked_to_pull_request():
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
        external_id="JIRA-104",
        source="jira",
        title="Add authentication",
        description="Users must be able to authenticate.",
    )

    link = RequirementPullRequest.objects.create(
        requirement=requirement,
        pull_request=pull_request,
    )

    assert link.requirement == requirement
    assert link.pull_request == pull_request

    assert requirement.pull_request_links.count() == 1
    assert pull_request.requirement_links.count() == 1

    assert (
        requirement.pull_request_links.first().pull_request
        == pull_request
    )

    assert (
        pull_request.requirement_links.first().requirement
        == requirement
    )


@pytest.mark.django_db
def test_evidence_can_point_to_changed_file():
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

    commit = Commit.objects.create(
        repository=repository,
        pull_request=pull_request,
        sha="c" * 40,
        message="Implement authentication",
        author="kilel",
        committed_at="2026-08-17T10:30:00Z",
    )

    changed_file = ChangedFile.objects.create(
        commit=commit,
        filename="users/views.py",
        status="modified",
        additions=20,
        deletions=5,
        changes=25,
        patch="@@ -1,5 +1,20 @@",
    )

    requirement = Requirement.objects.create(
        repository=repository,
        external_id="JIRA-104",
        source="jira",
        title="Authentication",
        description="Users must be able to authenticate.",
    )

    evidence = Evidence.objects.create(
        requirement=requirement,
        pull_request=pull_request,
        commit=commit,
        changed_file=changed_file,
        evidence_type="code",
        status="valid",
        description="Authentication logic was added.",
        metadata={
            "filename": "users/views.py",
        },
    )

    assert evidence.requirement == requirement
    assert evidence.pull_request == pull_request
    assert evidence.commit == commit
    assert evidence.changed_file == changed_file

    assert requirement.evidence.count() == 1
    assert pull_request.evidence.count() == 1
    assert commit.evidence.count() == 1
    assert changed_file.evidence.count() == 1


@pytest.mark.django_db
def test_verification_can_be_linked_to_evidence():
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
        external_id="JIRA-104",
        source="jira",
        title="Authentication",
        description="Users must be able to authenticate.",
    )

    evidence = Evidence.objects.create(
        requirement=requirement,
        pull_request=pull_request,
        evidence_type="code",
        status="valid",
        description="Authentication endpoint exists.",
    )

    verification = Verification.objects.create(
        requirement=requirement,
        pull_request=pull_request,
        status="verified",
        summary="Authentication requirement is implemented.",
        confidence=0.95,
    )

    verification_evidence = VerificationEvidence.objects.create(
        verification=verification,
        evidence=evidence,
    )

    assert (
        verification_evidence.verification
        == verification
    )

    assert (
        verification_evidence.evidence
        == evidence
    )

    assert verification.evidence_links.count() == 1
    assert evidence.verification_links.count() == 1

    assert (
        verification.evidence_links.first().evidence
        == evidence
    )

@pytest.mark.django_db
def test_complete_requirement_to_verification_chain():
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

    commit = Commit.objects.create(
        repository=repository,
        pull_request=pull_request,
        sha="c" * 40,
        message="Implement authentication",
        author="kilel",
        committed_at="2026-08-17T10:30:00Z",
    )

    changed_file = ChangedFile.objects.create(
        commit=commit,
        filename="users/views.py",
        status="modified",
        additions=20,
        deletions=5,
        changes=25,
        patch="@@ authentication implementation",
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

    RequirementPullRequest.objects.create(
        requirement=requirement,
        pull_request=pull_request,
    )

    evidence = Evidence.objects.create(
        requirement=requirement,
        pull_request=pull_request,
        commit=commit,
        changed_file=changed_file,
        evidence_type="code",
        status="valid",
        description=(
            "Authentication implementation "
            "was found in users/views.py."
        ),
    )

    verification = Verification.objects.create(
        requirement=requirement,
        pull_request=pull_request,
        status="verified",
        summary=(
            "The authentication requirement "
            "is implemented."
        ),
        confidence=0.95,
    )

    VerificationEvidence.objects.create(
        verification=verification,
        evidence=evidence,
    )

    # Requirement → PR
    assert (
        requirement.pull_request_links.first().pull_request
        == pull_request
    )

    # PR → Commit
    assert (
        pull_request.commits.first()
        == commit
    )

    # Commit → ChangedFile
    assert (
        commit.changed_files.first()
        == changed_file
    )

    # ChangedFile → Evidence
    assert (
        changed_file.evidence.first()
        == evidence
    )

    # Evidence → Verification
    assert (
        evidence.verification_links.first().verification
        == verification
    )

    # Requirement → Verification
    assert (
        requirement.verifications.first()
        == verification
    )

    assert verification.status == "verified"
    assert verification.confidence == 0.95