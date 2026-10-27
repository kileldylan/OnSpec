import pytest

from ACI_backend.ACIApp.models import (
    ChangedFile,
    Commit,
    Evidence,
    PullRequest,
    Repository,
    Requirement,
)
from ACI_backend.integrations.verification.service import (
    ingest_changed_file_evidence,
)


@pytest.mark.django_db
def test_ingest_changed_file_evidence_creates_code_evidence():
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

    commit = Commit.objects.create(
        repository=repository,
        pull_request=pull_request,
        sha="c" * 40,
        message="Add authentication",
        author="kilel",
        committed_at="2026-08-17T10:30:00Z",
    )

    changed_file = ChangedFile.objects.create(
        commit=commit,
        filename="users/views.py",
        status="modified",
        additions=10,
        deletions=3,
        changes=13,
        patch=(
            "@@ -1,3 +1,5 @@\n"
            "+def request_password_reset(email):\n"
            "+    send_reset_email(email)"
        ),
    )

    result = ingest_changed_file_evidence(
        requirement=requirement,
        pull_request=pull_request,
    )

    assert len(result) == 1

    evidence = result[0]

    assert evidence.requirement == requirement
    assert evidence.pull_request == pull_request
    assert evidence.commit == commit
    assert evidence.changed_file == changed_file

    assert evidence.evidence_type == "code"
    assert evidence.status == "valid"

    assert evidence.description == (
        "Changed file: users/views.py"
    )

    assert evidence.metadata == {
        "filename": "users/views.py",
        "status": "modified",
        "additions": 10,
        "deletions": 3,
        "changes": 13,
        "evidence_role": "implementation",
        "snippet": (
            "def request_password_reset(email):\n"
            "    send_reset_email(email)"
        ),
        "line_start": 1,
        "line_end": 2,
        "source_url": (
            "https://github.com/kilel/aci-demo/blob/"
            f"{'c' * 40}/users/views.py#L1-L2"
        ),
    }

    assert Evidence.objects.count() == 1


@pytest.mark.django_db
def test_ingest_changed_file_evidence_marks_readme_as_documentation():
    repository = Repository.objects.create(
        github_id=123457,
        owner="kilel",
        name="aci-demo",
        full_name="kilel/aci-demo",
        default_branch="main",
    )
    pull_request = PullRequest.objects.create(
        repository=repository,
        github_id=987655,
        number=2,
        title="Document password reset",
        author="kilel",
        source_branch="docs/reset",
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
        external_id="PROJ-124",
        source="jira",
        title="Add password reset",
    )
    commit = Commit.objects.create(
        repository=repository,
        pull_request=pull_request,
        sha="d" * 40,
        message="Document password reset",
        author="kilel",
        committed_at="2026-08-17T10:30:00Z",
    )
    ChangedFile.objects.create(
        commit=commit,
        filename="README.md",
        status="modified",
        additions=2,
        changes=2,
        patch="@@ -1 +1,3 @@\n+Password reset endpoint is available.",
    )

    evidence = ingest_changed_file_evidence(
        requirement=requirement,
        pull_request=pull_request,
    )[0]

    assert evidence.metadata["evidence_role"] == "documentation"
    assert evidence.metadata["snippet"] == ""
    assert "source_url" not in evidence.metadata


@pytest.mark.django_db
def test_ingest_changed_file_evidence_creates_evidence_for_multiple_files():
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

    commit = Commit.objects.create(
        repository=repository,
        pull_request=pull_request,
        sha="c" * 40,
        message="Add authentication",
        author="kilel",
        committed_at="2026-08-17T10:30:00Z",
    )

    ChangedFile.objects.create(
        commit=commit,
        filename="users/views.py",
        status="modified",
        additions=10,
        deletions=3,
        changes=13,
        patch="patch 1",
    )

    ChangedFile.objects.create(
        commit=commit,
        filename="users/serializers.py",
        status="added",
        additions=20,
        deletions=0,
        changes=20,
        patch="patch 2",
    )

    result = ingest_changed_file_evidence(
        requirement=requirement,
        pull_request=pull_request,
    )

    assert len(result) == 2
    assert Evidence.objects.count() == 2

    filenames = {
        evidence.changed_file.filename
        for evidence in result
    }

    assert filenames == {
        "users/views.py",
        "users/serializers.py",
    }


@pytest.mark.django_db
def test_ingest_changed_file_evidence_is_idempotent():
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

    commit = Commit.objects.create(
        repository=repository,
        pull_request=pull_request,
        sha="c" * 40,
        message="Add authentication",
        author="kilel",
        committed_at="2026-08-17T10:30:00Z",
    )

    changed_file = ChangedFile.objects.create(
        commit=commit,
        filename="users/views.py",
        status="modified",
        additions=10,
        deletions=3,
        changes=13,
        patch="patch",
    )

    first_result = ingest_changed_file_evidence(
        requirement=requirement,
        pull_request=pull_request,
    )

    second_result = ingest_changed_file_evidence(
        requirement=requirement,
        pull_request=pull_request,
    )

    assert len(first_result) == 1
    assert len(second_result) == 1

    assert first_result[0].id == second_result[0].id

    assert Evidence.objects.count() == 1