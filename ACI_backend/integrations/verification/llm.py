import json

import requests

from django.conf import settings

from ACI_backend.integrations.verification.service import (
    validate_evaluator_conclusion,
)
from ACI_backend.integrations.verification.errors import LLMProviderError


class OpenAIProvider:
    """Minimal OpenAI Chat Completions adapter for structured JSON output."""

    endpoint = "https://api.openai.com/v1/chat/completions"

    def __init__(self, api_key, *, timeout=30, session=None):
        self.api_key = api_key
        self.timeout = timeout
        self.session = session or requests

    def __call__(self, request, *, model):
        if not self.api_key:
            raise LLMProviderError("OPENAI_API_KEY is not configured.")

        response = self.session.post(
            self.endpoint,
            headers={
                "Authorization": f"Bearer {self.api_key}",
                "Content-Type": "application/json",
            },
            json={
                "model": model or settings.LLM_MODEL,
                "temperature": 0,
                "response_format": {"type": "json_object"},
                "messages": [
                    {
                        "role": "system",
                        "content": (
                            "Evaluate only the supplied evidence. Return JSON "
                            "matching response_schema. Never invent evidence. "
                            "For implementation claims, use only code evidence "
                            "whose metadata evidence_role is implementation and "
                            "whose metadata includes a non-empty added-code "
                            "snippet. Documentation changes such as README files "
                            "do not prove implementation. When describing code "
                            "evidence, cite its exact filename, line range, and "
                            "snippet from the supplied metadata."
                        ),
                    },
                    {
                        "role": "user",
                        "content": json.dumps(request),
                    },
                ],
            },
            timeout=self.timeout,
        )
        try:
            response.raise_for_status()
            return response.json()["choices"][0]["message"]["content"]
        except (requests.RequestException, ValueError, KeyError, IndexError) as error:
            raise LLMProviderError("OpenAI returned an unusable response.") from error


def create_openai_evaluator(*, timeout=30):
    """Create the configured OpenAI evaluator without exposing its key."""

    if not settings.OPENAI_API_KEY:
        raise LLMProviderError("OPENAI_API_KEY is not configured.")
    return LLMEvaluator(
        OpenAIProvider(settings.OPENAI_API_KEY, timeout=timeout),
        model=settings.LLM_MODEL,
    )


def build_evaluator_request(requirement, evidence):
    """Build a provider-neutral, evidence-grounded evaluator request."""

    evidence = list(evidence)
    return {
        "requirement": {
            "id": requirement.pk,
            "external_id": requirement.external_id,
            "title": requirement.title,
            "description": requirement.description,
        },
        "evidence": [
            {
                "id": item.pk,
                "type": item.evidence_type,
                "status": item.status,
                "description": item.description,
                "metadata": item.metadata,
                "commit_sha": item.commit.sha if item.commit_id else None,
                "changed_file": (
                    item.changed_file.filename
                    if item.changed_file_id
                    else None
                ),
            }
            for item in evidence
        ],
        "response_schema": {
            "status": "verified|partial|unverified|failed",
            "summary": (
                "string; implementation claims cite the exact filename, "
                "line range, and supplied code snippet"
            ),
            "confidence": "number between 0 and 1",
            "evidence_ids": "array of supplied evidence ids",
        },
    }


class LLMEvaluator:
    """Provider-neutral adapter for a structured, grounded LLM evaluator."""

    def __init__(self, provider, *, model=None):
        self.provider = provider
        self.model = model

    def evaluate(self, requirement, evidence):
        evidence = list(evidence)
        request = build_evaluator_request(requirement, evidence)
        try:
            response = self.provider(request, model=self.model)
        except Exception as error:
            raise LLMProviderError("LLM provider call failed.") from error
        try:
            response = json.loads(response) if isinstance(response, str) else response
        except (TypeError, ValueError, json.JSONDecodeError) as error:
            raise LLMProviderError("LLM returned an unreadable response.") from error

        if not isinstance(response, dict):
            raise LLMProviderError("LLM response must be a JSON object.")

        evidence_by_id = {item.pk: item for item in evidence}
        evidence_ids = response.get("evidence_ids")
        if not isinstance(evidence_ids, list):
            raise LLMProviderError("LLM response must include evidence_ids.")
        try:
            referenced_evidence = [evidence_by_id[item_id] for item_id in evidence_ids]
        except KeyError as error:
            raise LLMProviderError(
                "LLM referenced evidence outside the supplied collection."
            ) from error

        conclusion = {
            "status": response.get("status"),
            "summary": response.get("summary"),
            "confidence": response.get("confidence"),
            "evidence": referenced_evidence,
        }
        try:
            return validate_evaluator_conclusion(
                requirement=requirement,
                evidence=evidence,
                conclusion=conclusion,
            )
        except (TypeError, ValueError) as error:
            raise LLMProviderError("LLM conclusion failed contract validation.") from error