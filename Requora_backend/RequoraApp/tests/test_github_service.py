import pytest

from Requora_backend.RequoraApp.models import ChangedFile, Commit, Repository
from Requora_backend.integrations.github.service import ingest_commit_files


@pytest.mark.django_db
def test_ingest_commit_files_creates_changed_files():
    repository = Repository.objects.create(
        github_id=123456,
        owner="kilel",
        name="Requora-demo",
        full_name="kilel/Requora-demo",
        default_branch="main",
    )

    commit = Commit.objects.create(
        repository=repository,
        sha="aaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaa",
        message="Add authentication",
        author="kilel",
        committed_at="2026-08-17T10:00:00Z",
    )

    github_commit = {
        "files": [
            {
                "filename": "users/views.py",
                "status": "modified",
                "additions": 10,
                "deletions": 3,
                "changes": 13,
                "patch": "@@ -1,3 +1,10 @@",
            },
            {
                "filename": "users/serializers.py",
                "status": "added",
                "additions": 20,
                "deletions": 0,
                "changes": 20,
                "patch": "@@ -0,0 +1,20 @@",
            },
        ]
    }

    result = ingest_commit_files(
        commit=commit,
        github_commit=github_commit,
    )
    
    assert len(result) == 2

    assert ChangedFile.objects.count() == 2

    views_file = ChangedFile.objects.get(
        commit=commit,
        filename="users/views.py",
    )

    assert views_file.status == "modified"
    assert views_file.additions == 10
    assert views_file.deletions == 3
    assert views_file.changes == 13
    assert views_file.patch == "@@ -1,3 +1,10 @@"