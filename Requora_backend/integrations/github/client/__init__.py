import base64
import hashlib
import json
import re
import time
from urllib.parse import quote

import jwt
import requests
from requests.exceptions import RequestException

from django.conf import settings
from django.core.cache import cache
from django.utils import timezone
from django.utils.dateparse import parse_datetime

class GitHubAPIError(Exception):
    """Raised when a GitHub API request fails."""


class GitHubClient:
    BASE_URL = "https://api.github.com"

    def __init__(self, token=None, *, installation_id=None, timeout=None):
        self.token = token
        self.installation_id = installation_id
        self.timeout = timeout or settings.GITHUB_API_TIMEOUT
        self.session = requests.Session()
        self._installation_token = None

    def _app_jwt(self):
        if not settings.GITHUB_APP_ID or not settings.GITHUB_APP_PRIVATE_KEY:
            raise GitHubAPIError("GitHub App credentials are not configured.")
        private_key = settings.GITHUB_APP_PRIVATE_KEY.replace("\\n", "\n")
        now = int(time.time())
        try:
            return jwt.encode(
                {"iat": now - 60, "exp": now + 540, "iss": settings.GITHUB_APP_ID},
                private_key,
                algorithm="RS256",
            )
        except (jwt.PyJWTError, TypeError, ValueError) as exc:
            raise GitHubAPIError("GitHub App private key is invalid.") from exc

    def _get_installation_token(self):
        if self._installation_token:
            return self._installation_token
        if not self.installation_id:
            raise GitHubAPIError("GitHub App installation is not configured.")
        token_cache_key = (
            f"Requora:github:installation-token:{settings.GITHUB_APP_ID}:"
            f"{self.installation_id}"
        )
        cached_token = cache.get(token_cache_key)
        if (
            isinstance(cached_token, dict)
            and isinstance(cached_token.get("token"), str)
            and cached_token.get("token")
        ):
            self._installation_token = cached_token["token"]
            return self._installation_token

        url = (
            f"{self.BASE_URL}/app/installations/"
            f"{self.installation_id}/access_tokens"
        )
        try:
            response = self.session.post(
                url,
                headers={
                    "Accept": "application/vnd.github+json",
                    "Authorization": f"Bearer {self._app_jwt()}",
                    "X-GitHub-Api-Version": "2022-11-28",
                },
                timeout=self.timeout,
            )
            response.raise_for_status()
            payload = response.json()
        except (RequestException, ValueError) as exc:
            raise GitHubAPIError(
                "GitHub App installation token request failed."
            ) from exc
        token = payload.get("token") if isinstance(payload, dict) else None
        if not isinstance(token, str) or not token:
            raise GitHubAPIError(
                "GitHub did not return an installation access token."
            )
        self._installation_token = token
        expires_at = payload.get("expires_at") if isinstance(payload, dict) else None
        expires_at = parse_datetime(expires_at) if isinstance(expires_at, str) else None
        if expires_at is not None and timezone.is_aware(expires_at):
            timeout = int((expires_at - timezone.now()).total_seconds()) - 60
            if timeout > 0:
                cache.set(
                    token_cache_key,
                    {"token": token},
                    timeout=timeout,
                )
        return token

    def _cached_get(self, endpoint, *, timeout=300):
        auth_scope = (
            f"installation:{self.installation_id}"
            if self.installation_id
            else hashlib.sha256((self.token or "").encode()).hexdigest()
        )
        digest = hashlib.sha256(endpoint.encode()).hexdigest()
        key = f"Requora:github:read:{auth_scope}:{digest}"
        cached_result = cache.get(key)
        if cached_result is not None:
            return cached_result
        result = self._request(endpoint)
        serialized = json.dumps(result, separators=(",", ":"), ensure_ascii=False)
        if len(serialized.encode("utf-8")) <= settings.GITHUB_CACHE_MAX_BYTES:
            cache.set(key, result, timeout=timeout)
        return result

    def _request(self, endpoint, *, method="GET", payload=None):
        url = f"{self.BASE_URL}{endpoint}"

        headers = {
            "Accept": "application/vnd.github+json",
            "X-GitHub-Api-Version": "2022-11-28",
        }

        token = (
            self._get_installation_token()
            if self.installation_id
            else self.token
        )
        if token:
            headers["Authorization"] = f"Bearer {token}"

        try:
            request = getattr(self.session, method.lower())
            request_kwargs = {
                "headers": headers,
                "timeout": self.timeout,
            }
            if payload is not None:
                request_kwargs["json"] = payload
            response = request(url, **request_kwargs)
            response.raise_for_status()
            if response.status_code == 204:
                return {}
            return response.json()
        except RequestException as exc:
            response = exc.response
            status_code = response.status_code if response is not None else None
            try:
                error_payload = response.json() if response is not None else None
            except ValueError:
                error_payload = None
            message = (
                error_payload.get("message")
                if isinstance(error_payload, dict)
                else None
            )
            if isinstance(message, str):
                message = message[:500]
            details = f" ({status_code})" if status_code is not None else ""
            if message:
                details += f": {message}"
            raise GitHubAPIError(
                f"GitHub API request failed{details} for {method} {endpoint}."
            ) from exc
        except ValueError as exc:
            raise GitHubAPIError("GitHub API returned invalid JSON.") from exc

    def get_commit(self, owner, repository, sha):
        endpoint = f"/repos/{owner}/{repository}/commits/{sha}"
        if re.fullmatch(r"[0-9a-fA-F]{40,64}", sha):
            return self._cached_get(endpoint)
        return self._request(endpoint)

    def get_issue(self, owner, repository, issue_number):
        return self._request(
            f"/repos/{owner}/{repository}/issues/{issue_number}"
        )

    def list_installation_repositories(self):
        repositories = []
        page = 1
        while True:
            result = self._request(
                f"/installation/repositories?per_page=100&page={page}"
            )
            batch = result.get("repositories") if isinstance(result, dict) else None
            if not isinstance(batch, list):
                raise GitHubAPIError(
                    "GitHub returned an invalid installation repository list."
                )
            repositories.extend(batch)
            if len(batch) < 100:
                return repositories
            page += 1

    def get_pull_request_commits(self, owner, repository, pull_request_number):
        endpoint = f"/repos/{owner}/{repository}/pulls/{pull_request_number}/commits"
        return self._request(endpoint)

    def get_repository_tree(self, owner, repository, ref):
        endpoint = (
            f"/repos/{owner}/{repository}/git/trees/"
            f"{quote(ref, safe='')}?recursive=1"
        )
        if re.fullmatch(r"[0-9a-fA-F]{40,64}", ref):
            return self._cached_get(endpoint)
        return self._request(endpoint)

    def get_repository_file(self, owner, repository, path, ref):
        endpoint = (
            f"/repos/{owner}/{repository}/contents/"
            f"{quote(path, safe='/')}?ref={quote(ref, safe='')}"
        )
        result = (
            self._cached_get(endpoint)
            if re.fullmatch(r"[0-9a-fA-F]{40,64}", ref)
            else self._request(endpoint)
        )
        if result.get("encoding") != "base64" or not result.get("content"):
            return ""
        try:
            return base64.b64decode(result["content"]).decode("utf-8")
        except (ValueError, UnicodeDecodeError) as exc:
            raise GitHubAPIError(
                f"GitHub returned non-text content for {path}."
            ) from exc

    def list_check_runs(self, owner, repository, *, check_name, head_sha):
        endpoint = (
            f"/repos/{owner}/{repository}/commits/{head_sha}/check-runs"
            f"?check_name={quote(check_name, safe='')}&per_page=100"
        )
        return self._request(endpoint)

    def create_check_run(self, owner, repository, payload):
        return self._request(
            f"/repos/{owner}/{repository}/check-runs",
            method="POST",
            payload=payload,
        )

    def update_check_run(self, owner, repository, check_run_id, payload):
        return self._request(
            f"/repos/{owner}/{repository}/check-runs/{check_run_id}",
            method="PATCH",
            payload=payload,
        )

    def list_pull_request_comments(self, owner, repository, pull_request_number):
        return self._request(
            f"/repos/{owner}/{repository}/issues/{pull_request_number}/comments"
            "?per_page=100"
        )

    def get_issue_comment(self, owner, repository, comment_id):
        return self._request(
            f"/repos/{owner}/{repository}/issues/comments/{comment_id}"
        )

    def create_issue_comment(self, owner, repository, issue_number, body):
        return self._request(
            f"/repos/{owner}/{repository}/issues/{issue_number}/comments",
            method="POST",
            payload={"body": body},
        )

    def update_issue_comment(self, owner, repository, comment_id, body):
        return self._request(
            f"/repos/{owner}/{repository}/issues/comments/{comment_id}",
            method="PATCH",
            payload={"body": body},
        )

    def create_pull_request_comment(self, owner, repository, pull_request_number, body):
        return self.create_issue_comment(
            owner,
            repository,
            pull_request_number,
            body,
        )

    def update_pull_request_comment(self, owner, repository, comment_id, body):
        return self.update_issue_comment(
            owner,
            repository,
            comment_id,
            body,
        )
