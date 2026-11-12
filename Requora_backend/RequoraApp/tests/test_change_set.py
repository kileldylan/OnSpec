import pytest

from Requora_backend.RequoraApp.change_set import (
    build_pull_request_change_set,
)
from Requora_backend.RequoraApp.models import (
    ChangedFile,
    Commit,
    PullRequest,
    Repository,
)


@pytest.mark.django_db
def test_build_pull_request_change_set():
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
        message="Add authentication",
        author="kilel",
        committed_at="2026-08-17T10:00:00Z",
    )

    ChangedFile.objects.create(
        commit=commit,
        filename="users/views.py",
        status="modified",
        additions=10,
        deletions=3,
        changes=13,
        patch="@@ -1,3 +1,10 @@",
    )

    ChangedFile.objects.create(
        commit=commit,
        filename="users/serializers.py",
        status="added",
        additions=20,
        deletions=0,
        changes=20,
        patch="@@ -0,0 +1,20 @@",
    )

    result = build_pull_request_change_set(pull_request)

    assert result["summary"] == {
        "commit_count": 1,
        "file_count": 2,
        "additions": 30,
        "deletions": 3,
    }

    assert result["pull_request"]["number"] == 1

    assert len(result["commits"]) == 1

    assert len(result["files"]) == 2

    assert result["files"][0]["filename"] == "users/views.py"