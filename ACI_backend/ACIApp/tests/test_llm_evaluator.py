from unittest.mock import Mock

import pytest
import requests

from ACI_backend.ACIApp.models import Evidence, PullRequest, Requirement
from ACI_backend.integrations.verification.llm import (
    LLMProviderError,
    LLMEvaluator,
    OpenAIProvider,
    build_evaluator_request,
)


def create_evidence():
    requirement = Requirement(
        pk=1,
        external_id="AUTH-LLM",
        title="Users can authenticate",
        description="Users must be able to authenticate.",
    )
    pull_request = PullRequest(
        pk=2,
        number=7,
        head_sha="a" * 40,
    )
    evidence = Evidence(
        pk=3,
        requirement=requirement,
        pull_request=pull_request,
        evidence_type="code",
        status="valid",
        description="Authentication service exists.",
        metadata={
            "filename": "auth/service.py",
            "evidence_role": "implementation",
            "snippet": "def authenticate_user(credentials):",
            "line_start": 18,
            "line_end": 18,
            "source_url": "https://github.com/acme/app/blob/abc/auth/service.py#L18-L18",
        },
    )
    return requirement, [evidence]


def test_llm_request_contains_only_grounded_evidence():
    requirement, evidence = create_evidence()

    request = build_evaluator_request(requirement, evidence)

    assert request["requirement"]["external_id"] == "AUTH-LLM"
    assert request["evidence"] == [{
        "id": 3,
        "type": "code",
        "status": "valid",
        "description": "Authentication service exists.",
        "metadata": {
            "filename": "auth/service.py",
            "evidence_role": "implementation",
            "snippet": "def authenticate_user(credentials):",
            "line_start": 18,
            "line_end": 18,
            "source_url": "https://github.com/acme/app/blob/abc/auth/service.py#L18-L18",
        },
        "commit_sha": None,
        "changed_file": None,
    }]
    assert "evidence_ids" in request["response_schema"]


def test_llm_evaluator_maps_and_validates_evidence_ids():
    requirement, evidence = create_evidence()

    def provider(request, *, model):
        assert model == "test-model"
        assert request["evidence"][0]["id"] == 3
        return {
            "status": "partial",
            "summary": "Code evidence is present but tests are missing.",
            "confidence": 0.6,
            "evidence_ids": [3],
        }

    conclusion = LLMEvaluator(provider, model="test-model").evaluate(
        requirement,
        evidence,
    )

    assert conclusion["status"] == "partial"
    assert conclusion["evidence"] == evidence


def test_llm_evaluator_rejects_unknown_evidence_reference():
    requirement, evidence = create_evidence()

    def provider(request, *, model):
        return {
            "status": "verified",
            "summary": "Unsupported claim.",
            "confidence": 0.9,
            "evidence_ids": [999],
        }

    with pytest.raises(LLMProviderError, match="outside"):
        LLMEvaluator(provider).evaluate(requirement, evidence)


def test_llm_evaluator_preserves_provider_error_details():
    requirement, evidence = create_evidence()
    provider_error = LLMProviderError(
        "OpenAI API returned HTTP 429 (insufficient_quota).",
        status_code=429,
        provider_code="insufficient_quota",
    )

    def provider(request, *, model):
        raise provider_error

    with pytest.raises(LLMProviderError) as error:
        LLMEvaluator(provider).evaluate(requirement, evidence)

    assert error.value is provider_error
    assert error.value.status_code == 429
    assert error.value.provider_code == "insufficient_quota"


def test_llm_evaluator_returns_grounded_per_criterion_results():
    requirement, evidence = create_evidence()
    criterion = type(
        "Criterion",
        (),
        {"pk": 4, "text": "Users can authenticate."},
    )()

    def provider(request, *, model):
        assert request["criteria"] == [
            {"id": 4, "text": "Users can authenticate."},
        ]
        assert request["evidence"][0]["metadata"]["snippet"]
        return {
            "evaluations": [{
                "criterion_id": 4,
                "status": "satisfied",
                "summary": (
                    "Implemented in auth/service.py, line 18: "
                    "def authenticate_user(credentials):"
                ),
                "confidence": 0.9,
                "evidence_ids": [3],
            }],
        }

    result = LLMEvaluator(provider).evaluate_criteria(
        requirement,
        [criterion],
        evidence,
    )

    assert result[4]["status"] == "satisfied"
    assert result[4]["evidence"] == evidence


def test_llm_criterion_evaluation_rejects_satisfied_without_evidence():
    requirement, evidence = create_evidence()
    criterion = type(
        "Criterion",
        (),
        {"pk": 4, "text": "Users can authenticate."},
    )()
    evaluator = LLMEvaluator(
        lambda request, *, model: {
            "evaluations": [{
                "criterion_id": 4,
                "status": "satisfied",
                "summary": "Implemented.",
                "confidence": 0.9,
                "evidence_ids": [],
            }],
        }
    )

    with pytest.raises(LLMProviderError, match="without supporting evidence"):
        evaluator.evaluate_criteria(requirement, [criterion], evidence)


def test_openai_provider_extracts_structured_response():
    response = Mock()
    response.json.return_value = {
        "choices": [{"message": {"content": '{"status": "partial"}'}}],
    }
    session = Mock()
    session.post.return_value = response

    content = OpenAIProvider(
        "test-key",
        session=session,
    )(
        {"response_schema": {}},
        model="test-model",
    )

    assert content == '{"status": "partial"}'
    session.post.assert_called_once()
    assert session.post.call_args.kwargs["headers"]["Authorization"] == (
        "Bearer test-key"
    )


def test_openai_provider_retries_rate_limit_then_succeeds(monkeypatch):
    rate_limited = Mock()
    rate_limited.status_code = 429
    rate_limited.json.return_value = {
        "error": {
            "message": "Request rate limit reached.",
            "type": "rate_limit_error",
            "code": "rate_limit_exceeded",
        },
    }
    rate_limited.raise_for_status.side_effect = requests.HTTPError(
        response=rate_limited,
    )
    success = Mock()
    success.json.return_value = {
        "choices": [{"message": {"content": '{"status": "partial"}'}}],
    }
    session = Mock()
    session.post.side_effect = [rate_limited, success]
    sleep = Mock()
    monkeypatch.setattr(
        "ACI_backend.integrations.verification.llm.time.sleep",
        sleep,
    )

    result = OpenAIProvider("test-key", session=session)(
        {"response_schema": {}},
        model="test-model",
    )

    assert result == '{"status": "partial"}'
    assert session.post.call_count == 2
    sleep.assert_called_once_with(1)


def test_openai_provider_reports_quota_429_without_retrying(monkeypatch):
    response = Mock()
    response.status_code = 429
    response.json.return_value = {
        "error": {
            "message": "No quota remaining.",
            "type": "insufficient_quota",
            "code": "insufficient_quota",
        },
    }
    response.raise_for_status.side_effect = requests.HTTPError(
        response=response,
    )
    session = Mock()
    session.post.return_value = response
    sleep = Mock()
    monkeypatch.setattr(
        "ACI_backend.integrations.verification.llm.time.sleep",
        sleep,
    )

    with pytest.raises(LLMProviderError, match="insufficient_quota") as error:
        OpenAIProvider("test-key", session=session)(
            {"response_schema": {}},
            model="test-model",
        )

    assert error.value.status_code == 429
    assert error.value.provider_code == "insufficient_quota"
    session.post.assert_called_once()
    sleep.assert_not_called()