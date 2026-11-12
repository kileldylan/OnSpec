from Requora_backend.RequoraApp.models import PullRequest


def build_pull_request_change_set(pull_request):
    """
    Build a normalized representation of all changes
    associated with a pull request.
    """

    commits = (
        pull_request.commits
        .prefetch_related("changed_files")
        .all()
    )

    files = []

    total_additions = 0
    total_deletions = 0

    for commit in commits:
        for changed_file in commit.changed_files.all():
            files.append(
                {
                    "commit_sha": commit.sha,
                    "filename": changed_file.filename,
                    "status": changed_file.status,
                    "additions": changed_file.additions,
                    "deletions": changed_file.deletions,
                    "changes": changed_file.changes,
                    "patch": changed_file.patch,
                }
            )

            total_additions += changed_file.additions
            total_deletions += changed_file.deletions

    return {
        "pull_request": {
            "id": pull_request.github_id,
            "number": pull_request.number,
            "title": pull_request.title,
            "source_branch": pull_request.source_branch,
            "target_branch": pull_request.target_branch,
            "base_sha": pull_request.base_sha,
            "head_sha": pull_request.head_sha,
        },
        "commits": [
            {
                "sha": commit.sha,
                "message": commit.message,
                "author": commit.author,
            }
            for commit in commits
        ],
        "files": files,
        "summary": {
            "commit_count": len(commits),
            "file_count": len(files),
            "additions": total_additions,
            "deletions": total_deletions,
        },
    }