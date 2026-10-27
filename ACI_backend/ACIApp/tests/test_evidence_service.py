from unittest.mock import Mock

import pytest

from ACI_backend.ACIApp.models import (
    ChangedFile,
    Commit,
    Evidence,
    PullRequest,
    Repository,
    Requirement,
    RequirementCriterion,
    Verification,
)
from ACI_backend.integrations.verification.service import (
    collect_repository_code_evidence,
    ingest_changed_file_evidence,
)
from ACI_backend.integrations.verification.criteria import execute_criteria


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
def test_collect_repository_code_evidence_finds_implementation_outside_pr_diff():
    repository = Repository.objects.create(
        github_id=123458,
        owner="kilel",
        name="aci-demo",
        full_name="kilel/aci-demo",
        default_branch="main",
    )
    pull_request = PullRequest.objects.create(
        repository=repository,
        github_id=987656,
        number=3,
        title="Update project documentation",
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
        external_id="PROJ-125",
        source="jira",
        title="Password reset",
        description="Users can request a password reset email.",
    )
    RequirementCriterion.objects.create(
        requirement=requirement,
        text="A user can request a password reset.",
    )
    Commit.objects.create(
        repository=repository,
        pull_request=pull_request,
        sha=pull_request.head_sha,
        message="Update project documentation",
        author="kilel",
        committed_at="2026-08-17T10:30:00Z",
    )
    github_client = Mock()
    github_client.get_repository_tree.return_value = {
        "tree": [
            {"path": "README.md", "type": "blob", "size": 200},
            {"path": "tests/test_reset.py", "type": "blob", "size": 300},
            {"path": "accounts/password_reset.py", "type": "blob", "size": 500},
        ],
    }
    github_client.get_repository_file.return_value = (
        "def request_password_reset(email):\n"
        "    token = create_reset_token(email)\n"
        "    send_reset_email(email, token)\n"
    )

    evidence = collect_repository_code_evidence(
        requirement=requirement,
        pull_request=pull_request,
        github_client=github_client,
    )

    assert len(evidence) == 1
    assert evidence[0].changed_file is None
    assert evidence[0].metadata["filename"] == "accounts/password_reset.py"
    assert evidence[0].metadata["evidence_role"] == "implementation"
    assert evidence[0].metadata["line_start"] == 1
    assert evidence[0].metadata["line_end"] == 3
    assert "send_reset_email" in evidence[0].metadata["snippet"]
    assert evidence[0].metadata["source_url"].endswith(
        "/accounts/password_reset.py#L1-L3"
    )
    verification = Verification.objects.create(
        requirement=requirement,
        pull_request=pull_request,
    )
    criterion_result = execute_criteria(
        verification=verification,
        evidence=evidence,
    )[0]
    assert criterion_result.status == "satisfied"
    assert criterion_result.evidence_links.get().evidence == evidence[0]
    github_client.get_repository_file.assert_called_once_with(
        "kilel",
        "aci-demo",
        "accounts/password_reset.py",
        pull_request.head_sha,
    )

    repeated = collect_repository_code_evidence(
        requirement=requirement,
        pull_request=pull_request,
        github_client=github_client,
    )
    assert repeated[0].id == evidence[0].id


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