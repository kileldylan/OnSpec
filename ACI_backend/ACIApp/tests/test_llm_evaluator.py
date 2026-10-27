from unittest.mock import Mock

import pytest

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