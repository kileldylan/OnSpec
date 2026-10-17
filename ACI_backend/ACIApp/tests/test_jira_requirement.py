from unittest.mock import Mock, patch

import pytest

from ACI_backend.ACIApp.models import (
    PullRequest,
    Repository,
    Requirement,
    RequirementPullRequest,
)
from ACI_backend.integrations.jira.service import (
    ingest_jira_requirement,
    ingest_jira_requirements_for_pull_request,
)
from ACI_backend.integrations.jira.client import JiraAPIError, JiraClient
from ACI_backend.integrations.jira.utils import (
    extract_jira_issue_keys,
)


@pytest.mark.django_db
def test_ingest_jira_requirement_creates_requirement_and_links_pr():
    repository = Repository.objects.create(
        github_id=123456,
        owner="kilel",
        name="aci-demo",
        full_name="kilel/aci-demo",
        default_branch="main",
    )

    pull_request = PullRequest.objects.create(
        repository=repository,
        github_id=987654,
        number=1,
        title="Add authentication",
        author="kilel",
        source_branch="feature/auth",
        target_branch="main",
        base_sha="b" * 40,
        head_sha="a" * 40,
        state="open",
        is_merged=False,
        created_at="2026-08-17T10:00:00Z",
        updated_at="2026-08-17T10:00:00Z",
    )

    jira_issue = {
        "key": "PROJ-123",
        "fields": {
            "summary": "Add authentication",
            "description": "Users must be able to authenticate.",
            "status": {
                "name": "To Do",
            },
        },
    }

    requirement = ingest_jira_requirement(
        pull_request=pull_request,
        jira_issue=jira_issue,
    )

    assert requirement.external_id == "PROJ-123"
    assert requirement.source == "jira"
    assert requirement.title == "Add authentication"
    assert requirement.description == (
        "Users must be able to authenticate."
    )
    assert requirement.status == "open"

    assert Requirement.objects.count() == 1

    link = RequirementPullRequest.objects.get(
        requirement=requirement,
        pull_request=pull_request,
    )

    assert link.requirement == requirement
    assert link.pull_request == pull_request


@pytest.mark.django_db
def test_ingest_jira_requirement_extracts_criteria_from_stringified_doc_description():
    repository = Repository.objects.create(
        github_id=246810,
        owner="kilo",
        name="criteria-repo",
        full_name="kilo/criteria-repo",
        default_branch="main",
    )
    pull_request = PullRequest.objects.create(
        repository=repository,
        github_id=135791,
        number=11,
        title="Add login endpoint",
        author="kilel",
        source_branch="feature/login",
        target_branch="main",
        base_sha="b" * 40,
        head_sha="a" * 40,
        state="open",
        is_merged=False,
        created_at="2026-08-17T10:00:00Z",
        updated_at="2026-08-17T10:00:00Z",
    )

    jira_issue = {
        "key": "KIL-4",
        "fields": {
            "summary": "Add login endpoint",
            "description": "{'type': 'doc', 'version': 1, 'content': [{'type': 'paragraph', 'content': [{'type': 'text', 'text': 'Add a token-based login endpoint for the API using Django REST Framework.'}], 'attrs': {'localId': 'fa80e12a2a4a'}}, {'type': 'paragraph', 'content': [{'type': 'text', 'text': 'Acceptance criteria:'}], 'attrs': {'localId': '529ce8fdbe4c'}}, {'type': 'orderedList', 'attrs': {'order': 1, 'localId': '837d7c04dd35'}, 'content': [{'type': 'listItem', 'attrs': {'localId': 'e6504757a906'}, 'content': [{'type': 'paragraph', 'content': [{'type': 'text', 'text': 'POST /api/login accepts email and password.'}]}]}, {'type': 'listItem', 'attrs': {'localId': '4b52b3fc4d2e'}, 'content': [{'type': 'paragraph', 'content': [{'type': 'text', 'text': 'Valid credentials return HTTP 200 with a token.'}]}]}, {'type': 'listItem', 'attrs': {'localId': '7fbc4456266d'}, 'content': [{'type': 'paragraph', 'content': [{'type': 'text', 'text': 'Invalid credentials return HTTP 401.'}]}]}]}]}",
            "status": {"name": "To Do"},
        },
    }

    requirement = ingest_jira_requirement(
        pull_request=pull_request,
        jira_issue=jira_issue,
    )

    criteria = list(requirement.criteria.filter(is_active=True).order_by("order"))
    assert [criterion.text for criterion in criteria] == [
        "POST /api/login accepts email and password.",
        "Valid credentials return HTTP 200 with a token.",
        "Invalid credentials return HTTP 401.",
    ]


@pytest.mark.django_db
def test_sync_requirement_criteria_is_idempotent():
    repository = Repository.objects.create(
        github_id=314159,
        owner="oci",
        name="idempotent-repo",
        full_name="oci/idempotent-repo",
        default_branch="main",
    )
    pull_request = PullRequest.objects.create(
        repository=repository,
        github_id=222222,
        number=99,
        title="Login API",
        author="kilel",
        source_branch="feature/login",
        target_branch="main",
        base_sha="b" * 40,
        head_sha="a" * 40,
        state="open",
        is_merged=False,
        created_at="2026-08-17T10:00:00Z",
        updated_at="2026-08-17T10:00:00Z",
    )
    requirement = Requirement.objects.create(
        repository=repository,
        external_id="KIL-99",
        source="jira",
        title="Login API",
        description=(
            "Add a token-based login endpoint for the API using Django REST Framework. "
            "Acceptance criteria: 1. POST /api/login accepts email and password. "
            "2. Valid credentials return HTTP 200 with a token. "
            "3. Invalid credentials return HTTP 401."
        ),
    )

    from ACI_backend.integrations.verification.criteria import sync_requirement_criteria_from_text

    first_sync = sync_requirement_criteria_from_text(requirement=requirement, text=requirement.description)
    second_sync = sync_requirement_criteria_from_text(requirement=requirement, text=requirement.description)

    assert len(first_sync) == 3
    assert len(second_sync) == 0
    assert requirement.criteria.filter(is_active=True).count() == 3


@pytest.mark.django_db
def test_ingest_jira_requirement_extracts_criteria_from_atlassian_doc_description():
    repository = Repository.objects.create(
        github_id=246810,
        owner="kilo",
        name="criteria-repo",
        full_name="kilo/criteria-repo",
        default_branch="main",
    )
    pull_request = PullRequest.objects.create(
        repository=repository,
        github_id=135791,
        number=11,
        title="Add login endpoint",
        author="kilel",
        source_branch="feature/login",
        target_branch="main",
        base_sha="b" * 40,
        head_sha="a" * 40,
        state="open",
        is_merged=False,
        created_at="2026-08-17T10:00:00Z",
        updated_at="2026-08-17T10:00:00Z",
    )

    jira_issue = {
        "key": "KIL-4",
        "fields": {
            "summary": "Add login endpoint",
            "description": {
                "type": "doc",
                "content": [
                    {"type": "paragraph", "content": [{"type": "text", "text": "Add a token-based login endpoint for the API using Django REST Framework."}]},
                    {"type": "paragraph", "content": [{"type": "text", "text": "Acceptance criteria:"}]},
                    {"type": "bulletList", "content": [
                        {"type": "listItem", "content": [{"type": "paragraph", "content": [{"type": "text", "text": "POST /api/login accepts email and password."}]}]},
                        {"type": "listItem", "content": [{"type": "paragraph", "content": [{"type": "text", "text": "Valid credentials return HTTP 200 with a token."}]}]},
                        {"type": "listItem", "content": [{"type": "paragraph", "content": [{"type": "text", "text": "Invalid credentials return HTTP 401."}]}]},
                    ]},
                ],
            },
            "status": {"name": "To Do"},
        },
    }

    requirement = ingest_jira_requirement(
        pull_request=pull_request,
        jira_issue=jira_issue,
    )

    criteria = list(requirement.criteria.filter(is_active=True).order_by("order"))
    assert len(criteria) == 3
    assert [criterion.text for criterion in criteria] == [
        "POST /api/login accepts email and password.",
        "Valid credentials return HTTP 200 with a token.",
        "Invalid credentials return HTTP 401.",
    ]


def test_extract_jira_issue_keys():
    text = """
    Implements PROJ-123.
    Also addresses PROJ-456.
    """

    result = extract_jira_issue_keys(text)

    assert result == [
        "PROJ-123",
        "PROJ-456",
    ]


def test_extract_jira_issue_keys_removes_duplicates():
    text = """
    PROJ-123 is the main requirement.
    This PR also fixes PROJ-123.
    """

    result = extract_jira_issue_keys(text)

    assert result == ["PROJ-123"]


def test_extract_jira_issue_keys_returns_empty_for_no_match():
    text = "Fix authentication and improve error handling."

    result = extract_jira_issue_keys(text)

    assert result == []


def test_jira_client_fetches_issue_with_timeout_and_basic_auth():
    response = Mock()
    response.json.return_value = {"key": "PROJ-123", "fields": {}}
    response.raise_for_status.return_value = None
    client = JiraClient(
        base_url="https://example.atlassian.net",
        email="aci@example.com",
        api_token="test-token",
        timeout=7,
    )

    with patch.object(client.session, "get", return_value=response) as get:
        issue = client.get_issue("PROJ-123")

    assert issue["key"] == "PROJ-123"
    get.assert_called_once_with(
        "https://example.atlassian.net/rest/api/3/issue/PROJ-123",
        auth=("aci@example.com", "test-token"),
        headers={"Accept": "application/json"},
        timeout=7,
    )


@pytest.mark.django_db
def test_ingest_jira_requirements_for_pull_request():
    repository = Repository.objects.create(
        github_id=123456,
        owner="kilel",
        name="aci-demo",
        full_name="kilel/aci-demo",
        default_branch="main",
    )

    pull_request = PullRequest.objects.create(
        repository=repository,
        github_id=987654,
        number=1,
        title="Add authentication PROJ-123",
        author="kilel",
        source_branch="feature/auth",
        target_branch="main",
        base_sha="b" * 40,
        head_sha="a" * 40,
        state="open",
        is_merged=False,
        created_at="2026-08-17T10:00:00Z",
        updated_at="2026-08-17T10:00:00Z",
    )

    jira_client = Mock()

    jira_client.get_issue.return_value = {
        "key": "PROJ-123",
        "fields": {
            "summary": "Add authentication",
            "description": (
                "Users must be able to authenticate."
            ),
            "status": {
                "name": "To Do",
            },
        },
    }

    requirements = ingest_jira_requirements_for_pull_request(
        pull_request=pull_request,
        text=pull_request.title,
        jira_client=jira_client,
    )

    assert len(requirements) == 1

    requirement = requirements[0]

    assert requirement.external_id == "PROJ-123"
    assert requirement.source == "jira"
    assert requirement.title == "Add authentication"

    assert Requirement.objects.count() == 1

    assert RequirementPullRequest.objects.filter(
        requirement=requirement,
        pull_request=pull_request,
    ).exists()

    jira_client.get_issue.assert_called_once_with(
        "PROJ-123",
    )


@pytest.mark.django_db
def test_ingest_jira_requirements_for_pull_request_skips_missing_issue():
    repository = Repository.objects.create(
        github_id=123456,
        owner="kilel",
        name="aci-demo",
        full_name="kilel/aci-demo",
        default_branch="main",
    )

    pull_request = PullRequest.objects.create(
        repository=repository,
        github_id=987654,
        number=1,
        title="Fix auth PROJ-404 and PROJ-123",
        author="kilel",
        source_branch="feature/auth",
        target_branch="main",
        base_sha="b" * 40,
        head_sha="a" * 40,
        state="open",
        is_merged=False,
        created_at="2026-08-17T10:00:00Z",
        updated_at="2026-08-17T10:00:00Z",
    )

    jira_client = Mock()
    jira_client.get_issue.side_effect = [
        JiraAPIError("Jira issue not found."),
        {
            "key": "PROJ-123",
            "fields": {
                "summary": "Add authentication",
                "description": "Users must be able to authenticate.",
                "status": {
                    "name": "To Do",
                },
            },
        },
    ]

    requirements = ingest_jira_requirements_for_pull_request(
        pull_request=pull_request,
        text=pull_request.title,
        jira_client=jira_client,
    )

    assert [requirement.external_id for requirement in requirements] == [
        "PROJ-123",
    ]
    assert Requirement.objects.filter(external_id="PROJ-404").count() == 0
    assert Requirement.objects.filter(external_id="PROJ-123").count() == 1