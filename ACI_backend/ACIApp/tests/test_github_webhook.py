import hashlib
import hmac
import json
from unittest.mock import patch

import pytest
from django.conf import settings
from django.urls import reverse
from rest_framework.test import APIClient

from ACI_backend.ACIApp.models import Commit, PullRequest, Repository
from ACI_backend.integrations.github.client import GitHubAPIError


@pytest.fixture
def api_client():
    return APIClient()


def create_github_signature(payload):
    body = json.dumps(payload).encode()

    signature = hmac.new(
        settings.GITHUB_WEBHOOK_SECRET.encode(),
        body,
        hashlib.sha256,
    ).hexdigest()

    return f"sha256={signature}", body


@pytest.mark.django_db
def test_github_webhook_accepts_valid_signature(api_client):
    payload = {
        "zen": "Keep it logically awesome.",
    }

    signature, body = create_github_signature(payload)

    response = api_client.post(
        reverse("github-webhook"),
        data=body,
        content_type="application/json",
        HTTP_X_GITHUB_EVENT="ping",
        HTTP_X_HUB_SIGNATURE_256=signature,
    )

    assert response.status_code == 202

    assert response.json() == {
        "message": "Webhook event ignored.",
        "event": "ping",
    }


@pytest.mark.django_db
def test_github_push_webhook_is_acknowledged_as_ignored(api_client):
    payload = {"ref": "refs/heads/main"}
    signature, body = create_github_signature(payload)

    response = api_client.post(
        reverse("github-webhook"),
        data=body,
        content_type="application/json",
        HTTP_X_GITHUB_EVENT="push",
        HTTP_X_HUB_SIGNATURE_256=signature,
    )

    assert response.status_code == 202
    assert response.json() == {
        "message": "Webhook event ignored.",
        "event": "push",
    }


@pytest.mark.django_db
def test_github_webhook_rejects_invalid_signature(api_client):
    payload = {
        "action": "opened",
    }

    body = json.dumps(payload).encode()

    response = api_client.post(
        reverse("github-webhook"),
        data=body,
        content_type="application/json",
        HTTP_X_GITHUB_EVENT="pull_request",
        HTTP_X_HUB_SIGNATURE_256="sha256=invalid-signature",
    )

    assert response.status_code == 401

    assert response.json() == {
        "detail": "Invalid webhook signature.",
    }


@pytest.mark.django_db
@patch(
    "ACI_backend.integrations.github.webhooks.process_pull_request_event",
    side_effect=GitHubAPIError("GitHub API request failed."),
)
def test_github_webhook_reports_github_api_failure(_mock_process, api_client):
    payload = {
        "action": "opened",
        "repository": {},
        "pull_request": {},
    }
    signature, body = create_github_signature(payload)

    response = api_client.post(
        reverse("github-webhook"),
        data=body,
        content_type="application/json",
        HTTP_X_GITHUB_EVENT="pull_request",
        HTTP_X_HUB_SIGNATURE_256=signature,
    )

    assert response.status_code == 502
    assert response.json() == {"detail": "GitHub API request failed."}


@pytest.mark.django_db
def test_github_webhook_rejects_missing_signature(api_client):
    payload = {
        "action": "opened",
    }

    body = json.dumps(payload).encode()

    response = api_client.post(
        reverse("github-webhook"),
        data=body,
        content_type="application/json",
        HTTP_X_GITHUB_EVENT="pull_request",
    )

    assert response.status_code == 401

    assert response.json() == {
        "detail": "Invalid webhook signature.",
    }


@pytest.mark.django_db
@patch(
    "ACI_backend.integrations.github.service.GitHubClient.get_pull_request_commits"
)
def test_github_pull_request_creates_repository_and_pull_request(
    mock_get_commits,
    api_client,
):
    """
    Verify that a valid GitHub pull_request webhook creates
    the Repository and PullRequest records.

    The GitHub API itself is mocked because this test is testing
    our webhook/service/database logic, not GitHub's API.
    """

    mock_get_commits.return_value = []

    payload = {
        "action": "opened",
        "repository": {
            "id": 123456,
            "name": "aci-demo",
            "full_name": "kilel/aci-demo",
            "default_branch": "main",
            "owner": {
                "login": "kilel",
            },
        },
        "pull_request": {
            "id": 987654,
            "number": 1,
            "title": "Add authentication",
            "state": "open",
            "merged": False,
            "created_at": "2026-08-17T10:00:00Z",
            "updated_at": "2026-08-17T10:00:00Z",
            "user": {
                "login": "kilel",
            },
            "head": {
                "ref": "feature/auth",
                "sha": "aaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaa",
            },
            "base": {
                "ref": "main",
                "sha": "bbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbb",
            },
        },
    }

    signature, body = create_github_signature(payload)

    response = api_client.post(
        reverse("github-webhook"),
        data=body,
        content_type="application/json",
        HTTP_X_GITHUB_EVENT="pull_request",
        HTTP_X_HUB_SIGNATURE_256=signature,
    )

    assert response.status_code == 200

    repository = Repository.objects.get(
        github_id=123456
    )

    assert repository.full_name == "kilel/aci-demo"
    assert repository.owner == "kilel"
    assert repository.name == "aci-demo"
    assert repository.default_branch == "main"

    pull_request = PullRequest.objects.get(
        repository=repository,
        number=1,
    )

    assert pull_request.github_id == 987654
    assert pull_request.title == "Add authentication"
    assert pull_request.author == "kilel"
    assert pull_request.source_branch == "feature/auth"
    assert pull_request.target_branch == "main"
    assert pull_request.state == "open"
    assert pull_request.is_merged is False
    assert pull_request.base_sha == (
        "bbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbb"
    )
    assert pull_request.head_sha == (
        "aaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaa"
    )

    mock_get_commits.assert_called_once_with(
        owner="kilel",
        repository="aci-demo",
        pull_request_number=1,
    )


@pytest.mark.django_db
@patch(
    "ACI_backend.integrations.github.service.GitHubClient"
)
def test_github_pull_request_ingests_commits(
    mock_github_client,
    api_client,
):
    """
    Verify that commits returned by GitHub are persisted.
    """

    mock_github_client.return_value.get_pull_request_commits.return_value = [
        {
            "sha": "cccccccccccccccccccccccccccccccccccccccc",
            "commit": {
                "message": "Add authentication",
                "author": {
                    "name": "kilel",
                    "date": "2026-08-17T10:30:00Z",
                },
            },
        }
    ]

    payload = {
        "action": "opened",
        "repository": {
            "id": 123456,
            "name": "aci-demo",
            "full_name": "kilel/aci-demo",
            "default_branch": "main",
            "owner": {
                "login": "kilel",
            },
        },
        "pull_request": {
            "id": 987654,
            "number": 1,
            "title": "Add authentication",
            "state": "open",
            "merged": False,
            "created_at": "2026-08-17T10:00:00Z",
            "updated_at": "2026-08-17T10:00:00Z",
            "user": {
                "login": "kilel",
            },
            "head": {
                "ref": "feature/auth",
                "sha": "aaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaa",
            },
            "base": {
                "ref": "main",
                "sha": "bbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbb",
            },
        },
    }

    signature, body = create_github_signature(payload)

    response = api_client.post(
        reverse("github-webhook"),
        data=body,
        content_type="application/json",
        HTTP_X_GITHUB_EVENT="pull_request",
        HTTP_X_HUB_SIGNATURE_256=signature,
    )

    assert response.status_code == 200

    commit = Commit.objects.get(
        sha="cccccccccccccccccccccccccccccccccccccccc"
    )

    assert commit.message == "Add authentication"
    assert commit.author == "kilel"
    assert commit.repository.full_name == "kilel/aci-demo"

    mock_github_client.return_value.get_pull_request_commits.assert_called_once_with(
        owner="kilel",
        repository="aci-demo",
        pull_request_number=1,
    )