import json
import requests
from requests.exceptions import RequestException

from django.conf import settings

class GitHubAPIError(Exception):
    """Raised when a GitHub API request fails."""


class GitHubClient:
    BASE_URL = "https://api.github.com"

    def __init__(self, token=None, *, timeout=None):
        self.token = token
        self.timeout = timeout or settings.GITHUB_API_TIMEOUT
        self.session = requests.Session()

    def _request(self, endpoint):
        url = f"{self.BASE_URL}{endpoint}"

        headers = {
            "Accept": "application/vnd.github+json",
            "X-GitHub-Api-Version": "2022-11-28",
        }

        if self.token:
            headers["Authorization"] = f"Bearer {self.token}"

        try:
            response = self.session.get(
                url,
                headers=headers,
                timeout=self.timeout,
            )
            response.raise_for_status()
            return response.json()
        except RequestException as exc:
            raise GitHubAPIError("GitHub API request failed.") from exc

    def get_commit(self, owner, repository, sha):
        return self._request(f"/repos/{owner}/{repository}/commits/{sha}")

    def get_pull_request_commits(self, owner, repository, pull_request_number):
        endpoint = f"/repos/{owner}/{repository}/pulls/{pull_request_number}/commits"
        return self._request(endpoint)
