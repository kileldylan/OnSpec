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


def test_github_app_installation_token_authenticates_api_requests():
    with patch(
        "ACI_backend.integrations.github.client.requests.Session.post"
    ) as mock_post, patch(
        "ACI_backend.integrations.github.client.requests.Session.get"
    ) as mock_get:
        token_response = Mock()
        token_response.json.return_value = {"token": "installation-token"}
        token_response.raise_for_status.return_value = None
        mock_post.return_value = token_response

        check_response = Mock()
        check_response.json.return_value = {"check_runs": []}
        check_response.raise_for_status.return_value = None
        check_response.status_code = 200
        mock_get.return_value = check_response

        client = GitHubClient(installation_id=123)
        with patch.object(client, "_app_jwt", return_value="app-jwt"):
            result = client.list_check_runs(
                "aci",
                "delivery",
                check_name="ACI / Delivery Verification",
                head_sha="a" * 40,
            )

    assert result == {"check_runs": []}
    mock_post.assert_called_once()
    assert mock_post.call_args.kwargs["headers"]["Authorization"] == "Bearer app-jwt"
    assert mock_get.call_args.kwargs["headers"]["Authorization"] == (
        "Bearer installation-token"
    )