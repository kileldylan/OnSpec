from unittest.mock import Mock, patch

import pytest
import requests

from ACI_backend.integrations.github.client import GitHubAPIError, GitHubClient


@pytest.mark.django_db
def test_get_pull_request_commits():
    github_response = [
        {
            "sha": "aaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaa",
            "commit": {
                "message": "Add authentication",
                "author": {
                    "name": "kilel",
                },
            },
        }
    ]

    with patch(
        "ACI_backend.integrations.github.client.requests.Session.get"
    ) as mock_get:

        mock_response = Mock()
        mock_response.json.return_value = github_response
        mock_response.raise_for_status.return_value = None

        mock_get.return_value = mock_response

        client = GitHubClient(token="test-token")

        commits = client.get_pull_request_commits(
            owner="kilel",
            repository="aci-demo",
            pull_request_number=1,
        )

    mock_get.assert_called_once_with(
        "https://api.github.com/repos/"
        "kilel/aci-demo/pulls/1/commits",
        headers={
            "Accept": "application/vnd.github+json",
            "X-GitHub-Api-Version": "2022-11-28",
            "Authorization": "Bearer test-token",
        },
        timeout=15,
    )

    assert commits == github_response


def test_github_api_request_errors_are_wrapped():
    with patch(
        "ACI_backend.integrations.github.client.requests.Session.get"
    ) as mock_get:
        mock_response = Mock()
        mock_response.raise_for_status.side_effect = requests.HTTPError(
            "Unauthorized"
        )
        mock_get.return_value = mock_response

        with pytest.raises(GitHubAPIError):
            GitHubClient(token="test-token").get_pull_request_commits(
                owner="kilel",
                repository="aci-demo",
                pull_request_number=1,
            )