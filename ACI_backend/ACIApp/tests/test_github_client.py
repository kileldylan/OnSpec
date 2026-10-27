import base64
from unittest.mock import patch

import pytest

from ACI_backend.integrations.github.client import GitHubClient


@pytest.fixture
def github_client():
    return GitHubClient(token="test-token")


def test_get_commit_returns_github_commit(github_client):
    github_response = {
        "sha": "aaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaa",
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
            "aci-demo",
            "aaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaa",
        )

    assert result == github_response

    mock_request.assert_called_once_with(
        "/repos/kilel/aci-demo/commits/"
        "aaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaa"
    )


def test_get_repository_tree_uses_recursive_ref(github_client):
    with patch.object(
        github_client,
        "_request",
        return_value={"tree": []},
    ) as mock_request:
        result = github_client.get_repository_tree(
            "kilel",
            "aci-demo",
            "feature/reset",
        )

    assert result == {"tree": []}
    mock_request.assert_called_once_with(
        "/repos/kilel/aci-demo/git/trees/feature%2Freset?recursive=1"
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
            "aci-demo",
            "accounts/password_reset.py",
            "abc123",
        )

    assert result == "def request_password_reset():\n"
    mock_request.assert_called_once_with(
        "/repos/kilel/aci-demo/contents/accounts/password_reset.py?ref=abc123"
    )