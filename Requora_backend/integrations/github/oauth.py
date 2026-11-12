import requests

from django.conf import settings


class GitHubOAuthError(Exception):
    """Raised when GitHub cannot complete an OAuth account connection."""


def exchange_code(code):
    try:
        token_response = requests.post(
            "https://github.com/login/oauth/access_token",
            data={
                "client_id": settings.GITHUB_OAUTH_CLIENT_ID,
                "client_secret": settings.GITHUB_OAUTH_CLIENT_SECRET,
                "code": code,
                "redirect_uri": settings.GITHUB_OAUTH_REDIRECT_URI,
            },
            headers={"Accept": "application/json"},
            timeout=settings.GITHUB_API_TIMEOUT,
        )
        token_response.raise_for_status()
        token_data = token_response.json()
        if not isinstance(token_data, dict):
            raise GitHubOAuthError("GitHub returned an invalid OAuth response.")
        access_token = token_data.get("access_token")
        if not access_token:
            raise GitHubOAuthError("GitHub did not return an access token.")

        profile_response = requests.get(
            "https://api.github.com/user",
            headers={
                "Accept": "application/vnd.github+json",
                "Authorization": f"Bearer {access_token}",
                "X-GitHub-Api-Version": "2022-11-28",
            },
            timeout=settings.GITHUB_API_TIMEOUT,
        )
        profile_response.raise_for_status()
        profile = profile_response.json()
    except (requests.RequestException, ValueError) as exc:
        raise GitHubOAuthError("GitHub account verification failed.") from exc

    if (
        not isinstance(profile, dict)
        or not isinstance(profile.get("id"), int)
        or not isinstance(profile.get("login"), str)
        or not profile["login"]
    ):
        raise GitHubOAuthError("GitHub returned an invalid account profile.")
    return {"id": profile["id"], "login": profile["login"]}
