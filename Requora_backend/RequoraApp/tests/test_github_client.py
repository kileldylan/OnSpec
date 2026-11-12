import base64
from datetime import datetime, timedelta, timezone
from uuid import uuid4
from unittest.mock import Mock, patch

import pytest

from Requora_backend.integrations.github.client import GitHubClient


@pytest.fixture
def github_client():
    return GitHubClient(token="test-token")


def test_get_commit_returns_github_commit(github_client):
    sha = uuid4().hex + uuid4().hex[:8]
    github_response = {
        "sha": sha,
        "files": [
            {
                "filename": "users/views.py",
                "status": "modified",
                "additions": 10,
                "deletions": 3,
                "changes": 13,
                "patch": "@@ -1,3 +1,10 @@",
            }
        ],
    }

    with patch.object(
        github_client,
        "_request",
        return_value=github_response,
    ) as mock_request:

        result = github_client.get_commit(
            "kilel",
            "Requora-demo",
            sha,
        )

    assert result == github_response

    mock_request.assert_called_once_with(
        f"/repos/kilel/Requora-demo/commits/{sha}"
    )


def test_immutable_github_read_is_cached_across_clients():
    sha = uuid4().hex + uuid4().hex[:8]
    first_client = GitHubClient(token="test-token")
    second_client = GitHubClient(token="test-token")
    result = {"sha": sha, "files": []}

    with patch.object(first_client, "_request", return_value=result) as first_request:
        assert first_client.get_commit("kilel", "Requora-demo", sha) == result
    with patch.object(second_client, "_request") as second_request:
        assert second_client.get_commit("kilel", "Requora-demo", sha) == result

    first_request.assert_called_once()
    second_request.assert_not_called()


def test_get_repository_tree_uses_recursive_ref(github_client):
    with patch.object(
        github_client,
        "_request",
        return_value={"tree": []},
    ) as mock_request:
        result = github_client.get_repository_tree(
            "kilel",
            "Requora-demo",
            "feature/reset",
        )

    assert result == {"tree": []}
    mock_request.assert_called_once_with(
        "/repos/kilel/Requora-demo/git/trees/feature%2Freset?recursive=1"
    )


def test_get_repository_file_decodes_base64_content(github_client):
    encoded = base64.b64encode(b"def request_password_reset():\n").decode()
    with patch.object(
        github_client,
        "_request",
        return_value={"encoding": "base64", "content": encoded},
    ) as mock_request:
        result = github_client.get_repository_file(
            "kilel",
            "Requora-demo",
            "accounts/password_reset.py",
            "abc123",
        )

    assert result == "def request_password_reset():\n"
    mock_request.assert_called_once_with(
        "/repos/kilel/Requora-demo/contents/accounts/password_reset.py?ref=abc123"
    )


def test_installation_token_is_cached_between_clients():
    installation_id = uuid4().int % 1_000_000_000
    with patch(
        "Requora_backend.integrations.github.client.requests.Session.post"
    ) as mock_post:
        token_response = Mock()
        token_response.json.return_value = {
            "token": f"installation-token-{installation_id}",
            "expires_at": (
                datetime.now(timezone.utc) + timedelta(minutes=30)
            ).isoformat(),
        }
        token_response.raise_for_status.return_value = None
        mock_post.return_value = token_response

        first_client = GitHubClient(installation_id=installation_id)
        second_client = GitHubClient(installation_id=installation_id)
        with patch.object(first_client, "_app_jwt", return_value="app-jwt"):
            first_token = first_client._get_installation_token()
        second_token = second_client._get_installation_token()

    assert first_token == second_token
    mock_post.assert_called_once()