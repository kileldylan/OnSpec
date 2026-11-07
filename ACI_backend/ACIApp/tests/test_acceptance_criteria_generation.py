import json
from unittest.mock import Mock, patch

import pytest
from django.test import override_settings

from ACI_backend.ACIApp.models import (
    AcceptanceCriteriaGeneration,
    Repository,
    Requirement,
    RequirementCriterion,
    PullRequest,
)
from ACI_backend.integrations.github.criteria_generation import (
    CriteriaGenerationError,
    generate_acceptance_criteria,
    process_issue_comment_event,
)
from ACI_backend.integrations.github.service import link_pull_request_requirements
from ACI_backend.integrations.jira.service import ingest_jira_requirement


CRITERIA = [
    "A valid request returns the expected resource.",
    "A missing resource returns HTTP 404.",
    "An unauthenticated request returns HTTP 401.",
    "Automated tests cover successful and failed requests.",
]
GENERATED_CRITERIA = {
    "criteria": CRITERIA,
    "markdown": "\n".join(f"- [ ] {item}" for item in CRITERIA),
}


def issue_comment_payload(*, body, comment_id, action="created"):
    return {
        "action": action,
        "installation": {"id": 77},
        "repository": {
            "id": 101,
            "name": "requora",
            "full_name": "acme/requora",
            "default_branch": "main",
            "owner": {"login": "acme"},
        },
        "issue": {
            "id": 202,
            "number": 12,
            "title": "Add resource endpoint",
            "body": "The endpoint should return a resource.",
            "html_url": "https://github.com/acme/requora/issues/12",
            "state": "open",
            "user": {"login": "issue-author"},
        },
        "comment": {
            "id": comment_id,
            "body": body,
            "user": {"login": "issue-author"},
        },
        "sender": {
            "login": "issue-author",
            "author_association": "NONE",
        },
    }


@pytest.mark.django_db
@override_settings(
    ACCEPTANCE_CRITERIA_LLM_PROVIDER="openai",
    ACCEPTANCE_CRITERIA_LLM_MODEL="gpt-test",
    ACCEPTANCE_CRITERIA_LLM_API_KEY="test-key",
    ACCEPTANCE_CRITERIA_LLM_TIMEOUT=12,
)
def test_generate_acceptance_criteria_returns_validated_json_checklist():
    response = Mock()
    response.json.return_value = {
        "choices": [
            {
                "message": {
                    "content": json.dumps({"criteria": CRITERIA}),
                },
            },
        ],
    }
    response.raise_for_status.return_value = None

    with patch(
        "ACI_backend.integrations.github.criteria_generation.requests.post",
        return_value=response,
    ) as post:
        result = generate_acceptance_criteria(
            title="Add resource endpoint",
            body="The endpoint should return a resource.",
        )

    assert result == {
        "criteria": CRITERIA,
        "markdown": "\n".join(f"- [ ] {item}" for item in CRITERIA),
    }
    request = post.call_args.kwargs
    assert request["json"]["model"] == "gpt-test"
    assert request["json"]["response_format"] == {"type": "json_object"}
    assert request["timeout"] == 12
    assert "observable outcome" in request["json"]["messages"][0]["content"]


@pytest.mark.django_db
@override_settings(
    ACCEPTANCE_CRITERIA_LLM_PROVIDER="openai",
    ACCEPTANCE_CRITERIA_LLM_API_KEY="test-key",
)
def test_generate_acceptance_criteria_rejects_out_of_range_results():
    response = Mock()
    response.json.return_value = {
        "choices": [
            {"message": {"content": json.dumps({"criteria": CRITERIA[:3]})}},
        ],
    }
    response.raise_for_status.return_value = None

    with patch(
        "ACI_backend.integrations.github.criteria_generation.requests.post",
        return_value=response,
    ), pytest.raises(CriteriaGenerationError, match="between four and eight"):
        generate_acceptance_criteria(title="Feature", body="Details")


@pytest.mark.django_db
@patch(
    "ACI_backend.integrations.github.criteria_generation.generate_acceptance_criteria",
    return_value=GENERATED_CRITERIA,
)
@patch("ACI_backend.integrations.github.criteria_generation.GitHubClient")
def test_generate_command_posts_preview_and_stores_draft(
    mock_github_client,
    mock_generate,
):
    mock_github_client.return_value.create_issue_comment.return_value = {"id": 909}

    generation = process_issue_comment_event(
        issue_comment_payload(body="/requora generate", comment_id=808)
    )

    assert generation.status == "draft"
    assert generation.criteria == CRITERIA
    assert generation.preview_comment_id == 909
    assert generation.triggering_comment_id == 808
    assert generation.github_issue_id == 202
    assert generation.source == "github"
    preview = mock_github_client.return_value.create_issue_comment.call_args.args[3]
    assert "AI-generated acceptance criteria (preview)" in preview
    assert "- [ ] " + CRITERIA[0] in preview
    mock_generate.assert_called_once_with(
        title="Add resource endpoint",
        body="The endpoint should return a resource.",
        source="github",
    )


@pytest.mark.django_db
@override_settings(JIRA_BASE_URL="https://jira.example", JIRA_API_TOKEN="test-token")
@patch(
    "ACI_backend.integrations.github.criteria_generation.generate_acceptance_criteria",
    return_value=GENERATED_CRITERIA,
)
@patch("ACI_backend.integrations.github.criteria_generation.JiraClient")
@patch("ACI_backend.integrations.github.criteria_generation.GitHubClient")
def test_generate_from_jira_reads_linked_issue_and_persists_key(
    mock_github_client,
    mock_jira_client,
    mock_generate,
):
    mock_github_client.return_value.create_issue_comment.return_value = {"id": 909}
    mock_jira_client.return_value.get_issue.return_value = {
        "key": "PROJ-9",
        "fields": {
            "summary": "Add resource endpoint",
            "description": {
                "type": "doc",
                "content": [
                    {
                        "type": "paragraph",
                        "content": [{"type": "text", "text": "Return resources."}],
                    },
                ],
            },
        },
    }

    generation = process_issue_comment_event(
        issue_comment_payload(
            body="/requora generate from jira PROJ-9",
            comment_id=818,
        )
    )

    assert generation.source == "jira"
    assert generation.jira_issue_key == "PROJ-9"
    mock_jira_client.return_value.get_issue.assert_called_once_with("PROJ-9")
    mock_generate.assert_called_once_with(
        title="Add resource endpoint (PROJ-9)",
        body="Return resources.",
        source="jira",
    )


@pytest.mark.django_db
@patch("ACI_backend.integrations.github.criteria_generation.GitHubClient")
def test_accept_reply_saves_edits_and_makes_criteria_available(mock_github_client):
    repository = Repository.objects.create(
        github_id=101,
        owner="acme",
        name="requora",
        full_name="acme/requora",
        github_installation_id=77,
    )
    generation = AcceptanceCriteriaGeneration.objects.create(
        repository=repository,
        github_issue_id=202,
        github_issue_number=12,
        source="github",
        version=1,
        criteria=CRITERIA,
        markdown="\n".join(f"- [ ] {item}" for item in CRITERIA),
        issue_title="Add resource endpoint",
        issue_body="The endpoint should return a resource.",
        triggering_comment_id=808,
        preview_comment_id=909,
        requested_by_login="issue-author",
    )
    edited = [
        "A valid request returns HTTP 200 with a resource body.",
        "A missing resource returns HTTP 404.",
        "An unauthenticated request returns HTTP 401.",
        "Automated tests cover the endpoint outcomes.",
    ]

    acceptance_payload = issue_comment_payload(
        body="/requora accept\n"
        + "\n".join(f"- [ ] {item}" for item in edited),
        comment_id=810,
    )
    result = process_issue_comment_event(acceptance_payload)
    retried_result = process_issue_comment_event(acceptance_payload)

    generation.refresh_from_db()
    assert result.pk == generation.pk
    assert retried_result.pk == generation.pk
    assert generation.status == "accepted"
    assert generation.approval_comment_id == 810
    assert generation.criteria == edited
    requirement = Requirement.objects.get(
        repository=repository,
        source="github",
        external_id="12",
    )
    assert list(
        requirement.criteria.filter(is_active=True)
        .order_by("order")
        .values_list("text", flat=True)
    ) == edited
    assert mock_github_client.return_value.update_issue_comment.call_count == 2
    mock_github_client.return_value.create_issue_comment.assert_not_called()


@pytest.mark.django_db
@patch("ACI_backend.integrations.github.criteria_generation.GitHubClient")
def test_plain_accept_reply_saves_preview_criteria(mock_github_client):
    repository = Repository.objects.create(
        github_id=102,
        owner="acme",
        name="requora-plain-accept",
        full_name="acme/requora-plain-accept",
        github_installation_id=78,
    )
    generation = AcceptanceCriteriaGeneration.objects.create(
        repository=repository,
        github_issue_id=203,
        github_issue_number=13,
        source="github",
        version=1,
        criteria=CRITERIA,
        markdown="\n".join(f"- [ ] {item}" for item in CRITERIA),
        issue_title="Add resource endpoint",
        issue_body="The endpoint should return a resource.",
        triggering_comment_id=809,
        preview_comment_id=910,
        requested_by_login="issue-author",
    )

    payload = issue_comment_payload(body="accept", comment_id=811)
    payload["repository"] = {
        "id": 102,
        "name": "requora-plain-accept",
        "full_name": "acme/requora-plain-accept",
        "default_branch": "main",
        "owner": {"login": "acme"},
    }
    payload["issue"].update({"id": 203, "number": 13})
    payload["installation"] = {"id": 78}

    process_issue_comment_event(
        payload
    )

    generation.refresh_from_db()
    assert generation.status == "accepted"
    assert generation.criteria == CRITERIA


@pytest.mark.django_db
def test_pull_request_linking_prefers_accepted_generated_issue_criteria():
    repository = Repository.objects.create(
        github_id=111,
        owner="acme",
        name="generated",
        full_name="acme/generated",
    )
    pull_request = PullRequest.objects.create(
        repository=repository,
        github_id=222,
        number=23,
        title="Implement endpoint",
        author="dev",
        source_branch="feature",
        target_branch="main",
        base_sha="b" * 40,
        head_sha="a" * 40,
        state="open",
        is_merged=False,
        created_at="2026-10-28T07:00:00Z",
        updated_at="2026-10-28T07:00:00Z",
    )
    requirement = Requirement.objects.create(
        repository=repository,
        source="github",
        external_id="12",
        title="Add resource endpoint",
    )
    RequirementCriterion.objects.create(
        requirement=requirement,
        text="Raw issue criteria that should not be used.",
    )
    generation = AcceptanceCriteriaGeneration.objects.create(
        repository=repository,
        github_issue_id=202,
        github_issue_number=12,
        jira_issue_key="PROJ-9",
        source="github",
        version=1,
        status="accepted",
        criteria=CRITERIA,
        markdown="\n".join(f"- [ ] {item}" for item in CRITERIA),
        issue_title="Add resource endpoint",
        issue_body="Raw issue body",
        triggering_comment_id=808,
        requested_by_login="issue-author",
        accepted_by_login="issue-author",
        accepted_at="2026-10-28T07:00:00Z",
    )

    linked = link_pull_request_requirements(
        pull_request=pull_request,
        payload={
            "pull_request": {
                "title": "Implement endpoint",
                "body": "Closes #12",
            },
        },
        github_client=Mock(),
    )

    assert linked == [requirement]
    assert generation.criteria == list(
        requirement.criteria.filter(is_active=True)
        .order_by("order")
        .values_list("text", flat=True)
    )


@pytest.mark.django_db
def test_jira_ingestion_prefers_accepted_generated_criteria():
    repository = Repository.objects.create(
        github_id=121,
        owner="acme",
        name="jira-generated",
        full_name="acme/jira-generated",
    )
    pull_request = PullRequest.objects.create(
        repository=repository,
        github_id=232,
        number=24,
        title="Implement endpoint",
        author="dev",
        source_branch="feature",
        target_branch="main",
        base_sha="b" * 40,
        head_sha="a" * 40,
        state="open",
        is_merged=False,
        created_at="2026-10-28T07:00:00Z",
        updated_at="2026-10-28T07:00:00Z",
    )
    AcceptanceCriteriaGeneration.objects.create(
        repository=repository,
        github_issue_id=333,
        github_issue_number=25,
        jira_issue_key="PROJ-9",
        source="jira",
        version=1,
        status="accepted",
        criteria=CRITERIA,
        markdown="\n".join(f"- [ ] {item}" for item in CRITERIA),
        issue_title="Add resource endpoint",
        triggering_comment_id=888,
        requested_by_login="issue-author",
        accepted_by_login="issue-author",
        accepted_at="2026-10-28T07:00:00Z",
    )

    requirement = ingest_jira_requirement(
        pull_request=pull_request,
        jira_issue={
            "key": "PROJ-9",
            "fields": {
                "summary": "Add resource endpoint",
                "description": "Raw Jira acceptance criteria.",
            },
        },
    )

    assert list(
        requirement.criteria.filter(is_active=True)
        .order_by("order")
        .values_list("text", flat=True)
    ) == CRITERIA
