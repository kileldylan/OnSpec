from unittest.mock import patch
from urllib.parse import parse_qs, urlparse

import pytest
from django.contrib.auth import get_user_model
from django.urls import reverse
from rest_framework.test import APIClient

from ACI_backend.ACIApp.models import GitHubAccount, PullRequest, Repository
from ACI_backend.integrations.github.service import process_pull_request_event


@pytest.mark.django_db
def test_github_connect_requires_login(settings):
    settings.GITHUB_OAUTH_CLIENT_ID = "oauth-client-id"

    response = APIClient().get(reverse("github-oauth-connect"))

    assert response.status_code in {401, 403}


@pytest.mark.django_db
def test_github_connect_returns_authorization_url_and_session_state(settings):
    settings.GITHUB_OAUTH_CLIENT_ID = "oauth-client-id"
    settings.GITHUB_OAUTH_CLIENT_SECRET = "oauth-client-secret"
    settings.GITHUB_OAUTH_REDIRECT_URI = (
        "https://on-spec.vercel.app/api/auth/github/callback/"
    )
    user = get_user_model().objects.create_user(
        username="aci-user",
        email="aci@example.com",
        password="strong-password-123",
    )
    client = APIClient()
    client.force_login(user)

    response = client.get(reverse("github-oauth-connect"))

    assert response.status_code == 200
    query = parse_qs(urlparse(response.json()["authorization_url"]).query)
    assert query["client_id"] == ["oauth-client-id"]
    assert query["redirect_uri"] == [settings.GITHUB_OAUTH_REDIRECT_URI]
    assert query["scope"] == ["read:user"]
    assert query["state"] == [client.session["github_oauth_state"]]
    assert client.session["github_oauth_mode"] == "link"


@pytest.mark.django_db
def test_github_login_returns_authorization_url_for_anonymous_user(settings):
    settings.GITHUB_OAUTH_CLIENT_ID = "oauth-client-id"
    settings.GITHUB_OAUTH_CLIENT_SECRET = "oauth-client-secret"
    client = APIClient()

    response = client.get(reverse("github-oauth-login"))

    assert response.status_code == 200
    query = parse_qs(urlparse(response.json()["authorization_url"]).query)
    assert query["client_id"] == ["oauth-client-id"]
    assert query["scope"] == ["read:user"]
    assert query["state"] == [client.session["github_oauth_state"]]
    assert client.session["github_oauth_mode"] == "login"


@pytest.mark.django_db
def test_github_login_reports_missing_oauth_configuration(settings):
    settings.GITHUB_OAUTH_CLIENT_ID = ""
    settings.GITHUB_OAUTH_CLIENT_SECRET = ""

    response = APIClient().get(reverse("github-oauth-login"))

    assert response.status_code == 503
    assert response.json() == {
        "detail": "GitHub account connection is not configured."
    }


@pytest.mark.django_db
@patch(
    "ACI_backend.api.auth.exchange_code",
    return_value={"id": 1234, "login": "kileldylan"},
)
def test_github_callback_links_account_and_matching_repositories(
    _exchange_code,
    settings,
):
    settings.FRONTEND_URL = "https://on-spec.vercel.app"
    user = get_user_model().objects.create_user(
        username="aci-user",
        email="different@example.com",
        password="strong-password-123",
    )
    owned_repository = Repository.objects.create(
        github_id=9871,
        owner="kileldylan",
        name="aci_test",
        full_name="kileldylan/aci_test",
    )
    authored_repository = Repository.objects.create(
        github_id=9872,
        owner="an-org",
        name="another-repo",
        full_name="an-org/another-repo",
    )
    PullRequest.objects.create(
        repository=authored_repository,
        github_id=12345,
        number=14,
        title="KIL-6 Password reset",
        author="kileldylan",
        source_branch="feature/password-reset",
        target_branch="main",
        base_sha="b" * 40,
        head_sha="a" * 40,
        state="open",
        is_merged=False,
        created_at="2026-10-27T10:00:00Z",
        updated_at="2026-10-27T10:00:00Z",
    )
    client = APIClient()
    client.force_login(user)
    session = client.session
    session["github_oauth_state"] = "valid-state"
    session["github_oauth_mode"] = "link"
    session.save()

    response = client.get(
        reverse("github-oauth-callback"),
        {"state": "valid-state", "code": "oauth-code"},
    )

    assert response.status_code == 302
    assert response.url == "https://on-spec.vercel.app/?github=connected"
    assert GitHubAccount.objects.get(user=user).github_login == "kileldylan"
    assert owned_repository.members.filter(pk=user.pk).exists()
    assert authored_repository.members.filter(pk=user.pk).exists()

    current_user_response = client.get(reverse("auth-me"))
    assert current_user_response.json()["user"]["github_login"] == "kileldylan"
    repositories_response = client.get(reverse("repository-list"))
    assert {item["id"] for item in repositories_response.json()} == {
        owned_repository.id,
        authored_repository.id,
    }


@pytest.mark.django_db
@patch(
    "ACI_backend.api.auth.exchange_code",
    return_value={"id": 555123, "login": "new-github-user"},
)
def test_github_login_creates_user_and_authenticates_by_github_id(
    _exchange_code,
    settings,
):
    settings.FRONTEND_URL = "https://on-spec.vercel.app"
    client = APIClient()
    session = client.session
    session["github_oauth_state"] = "valid-login-state"
    session["github_oauth_mode"] = "login"
    session.save()

    response = client.get(
        reverse("github-oauth-callback"),
        {"state": "valid-login-state", "code": "oauth-code"},
    )

    user = get_user_model().objects.get(username="github-555123")
    assert response.status_code == 302
    assert response.url == "https://on-spec.vercel.app/"
    assert GitHubAccount.objects.get(user=user).github_login == "new-github-user"
    assert client.get(reverse("auth-me")).json()["user"]["id"] == user.id


@pytest.mark.django_db
@patch(
    "ACI_backend.api.auth.exchange_code",
    return_value={"id": 555123, "login": "renamed-github-user"},
)
def test_github_login_reuses_existing_github_account(_exchange_code, settings):
    settings.FRONTEND_URL = "https://on-spec.vercel.app"
    user = get_user_model().objects.create_user(
        username="github-555123",
        email="",
        password=None,
    )
    GitHubAccount.objects.create(
        user=user,
        github_id=555123,
        github_login="old-github-login",
    )
    client = APIClient()
    session = client.session
    session["github_oauth_state"] = "valid-login-state"
    session["github_oauth_mode"] = "login"
    session.save()

    response = client.get(
        reverse("github-oauth-callback"),
        {"state": "valid-login-state", "code": "oauth-code"},
    )

    assert response.status_code == 302
    assert get_user_model().objects.count() == 1
    assert client.get(reverse("auth-me")).json()["user"]["id"] == user.id
    assert GitHubAccount.objects.get(user=user).github_login == "renamed-github-user"


@pytest.mark.django_db
def test_github_callback_rejects_invalid_state():
    user = get_user_model().objects.create_user(
        username="aci-user",
        email="aci@example.com",
        password="strong-password-123",
    )
    client = APIClient()
    client.force_login(user)
    session = client.session
    session["github_oauth_state"] = "expected-state"
    session["github_oauth_mode"] = "link"
    session.save()

    response = client.get(
        reverse("github-oauth-callback"),
        {"state": "attacker-state", "code": "oauth-code"},
    )

    assert response.status_code == 302
    assert response.url.endswith("/?github=invalid_state")
    assert not GitHubAccount.objects.exists()


@pytest.mark.django_db
@patch(
    "ACI_backend.api.auth.exchange_code",
    return_value={"id": 9876, "login": "another-account"},
)
def test_github_callback_cannot_replace_linked_github_identity(
    _exchange_code,
):
    user = get_user_model().objects.create_user(
        username="aci-user",
        email="aci@example.com",
        password="strong-password-123",
    )
    existing_account = GitHubAccount.objects.create(
        user=user,
        github_id=9875,
        github_login="original-account",
    )
    client = APIClient()
    client.force_login(user)
    session = client.session
    session["github_oauth_state"] = "valid-state"
    session.save()

    response = client.get(
        reverse("github-oauth-callback"),
        {"state": "valid-state", "code": "oauth-code"},
    )

    assert response.url.endswith("/?github=account_mismatch")
    existing_account.refresh_from_db()
    assert existing_account.github_id == 9875
    assert existing_account.github_login == "original-account"


@pytest.mark.django_db
@patch(
    "ACI_backend.integrations.github.service.GitHubClient.get_pull_request_commits",
    return_value=[],
)
def test_webhook_grants_repository_access_to_linked_pr_author(
    _get_commits,
):
    user = get_user_model().objects.create_user(
        username="aci-user",
        email="aci@example.com",
        password="strong-password-123",
    )
    GitHubAccount.objects.create(
        user=user,
        github_id=9876,
        github_login="kileldylan",
    )

    process_pull_request_event(
        {
            "repository": {
                "id": 9877,
                "name": "aci_test",
                "full_name": "an-org/aci_test",
                "default_branch": "main",
                "owner": {"login": "an-org"},
            },
            "pull_request": {
                "id": 9878,
                "number": 14,
                "title": "KIL-6 Add a password reset functionality",
                "state": "open",
                "merged": False,
                "created_at": "2026-10-27T10:00:00Z",
                "updated_at": "2026-10-27T10:00:00Z",
                "user": {"login": "kileldylan"},
                "head": {
                    "ref": "feature/password-reset",
                    "sha": "a" * 40,
                },
                "base": {"ref": "main", "sha": "b" * 40},
            },
        }
    )

    repository = Repository.objects.get(full_name="an-org/aci_test")
    assert repository.members.filter(pk=user.pk).exists()
