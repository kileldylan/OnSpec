import json
import time

import requests

from django.conf import settings

from ACI_backend.integrations.verification.service import (
    validate_evaluator_conclusion,
)
from ACI_backend.integrations.verification.errors import LLMProviderError


class OpenAIProvider:
    """Minimal OpenAI Chat Completions adapter for structured JSON output."""

    endpoint = "https://api.openai.com/v1/chat/completions"
    max_rate_limit_retries = 2

    def __init__(self, api_key, *, timeout=30, session=None):
        self.api_key = api_key
        self.timeout = timeout
        self.session = session or requests

    def __call__(self, request, *, model):
        if not self.api_key:
            raise LLMProviderError("OPENAI_API_KEY is not configured.")

        for attempt in range(self.max_rate_limit_retries + 1):
            try:
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
                                    "snippet from the supplied metadata. Evaluate every "
                                    "acceptance criterion independently. Mark a criterion "
                                    "missing or partial when its behavior is not supported "
                                    "by the supplied evidence; never infer that one "
                                    "criterion is satisfied because another is."
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
                response.raise_for_status()
            except requests.HTTPError as error:
                provider_error = self._provider_error(response)
                retryable = (
                    response.status_code == 429
                    and provider_error["code"] != "insufficient_quota"
                    and provider_error["type"] != "insufficient_quota"
                    and (
                        provider_error["code"] == "rate_limit_exceeded"
                        or provider_error["type"] == "rate_limit_error"
                    )
                )
                if retryable and attempt < self.max_rate_limit_retries:
                    retry_after = response.headers.get("Retry-After")
                    try:
                        delay = float(retry_after)
                    except (TypeError, ValueError):
                        delay = 2**attempt
                    if 0 <= delay <= 5:
                        time.sleep(delay)
                        continue
                raise LLMProviderError(
                    self._format_provider_error(response.status_code, provider_error),
                    status_code=response.status_code,
                    provider_code=provider_error["code"],
                    provider_type=provider_error["type"],
                ) from error
            except requests.RequestException as error:
                raise LLMProviderError("OpenAI request failed.") from error

            try:
                return response.json()["choices"][0]["message"]["content"]
            except (ValueError, KeyError, IndexError, TypeError) as error:
                raise LLMProviderError(
                    "OpenAI returned an unusable response."
                ) from error

        raise LLMProviderError("OpenAI request failed after rate-limit retries.")

    @staticmethod
    def _provider_error(response):
        try:
            error = response.json().get("error", {})
        except (ValueError, AttributeError):
            error = {}
        if not isinstance(error, dict):
            error = {}
        return {
            "code": error.get("code") if isinstance(error.get("code"), str) else None,
            "type": error.get("type") if isinstance(error.get("type"), str) else None,
            "message": (
                error.get("message")[:300]
                if isinstance(error.get("message"), str)
                else None
            ),
        }

    @staticmethod
    def _format_provider_error(status_code, provider_error):
        details = [
            item
            for item in (provider_error["code"], provider_error["type"])
            if item
        ]
        description = f"OpenAI API returned HTTP {status_code}"
        if details:
            description += f" ({', '.join(details)})"
        if provider_error["message"]:
            description += f": {provider_error['message']}"
        return description


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
        except LLMProviderError:
            raise
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

    def evaluate_criteria(self, requirement, criteria, evidence):
        """Evaluate every criterion against only the supplied evidence."""
        criteria = list(criteria)
        evidence = list(evidence)
        request = {
            "requirement": {
                "id": requirement.pk,
                "external_id": requirement.external_id,
                "title": requirement.title,
                "description": requirement.description,
            },
            "criteria": [
                {"id": criterion.pk, "text": criterion.text}
                for criterion in criteria
            ],
            "evidence": [
                {
                    "id": item.pk,
                    "type": item.evidence_type,
                    "description": item.description,
                    "metadata": item.metadata,
                    "filename": (
                        item.changed_file.filename
                        if item.changed_file_id
                        else (item.metadata or {}).get("filename")
                    ),
                    "commit_sha": item.commit.sha if item.commit_id else None,
                }
                for item in evidence
            ],
            "response_schema": {
                "evaluations": [
                    {
                        "criterion_id": "supplied criterion id",
                        "status": "satisfied|partial|missing|not_applicable|failed",
                        "summary": (
                            "string; implementation evidence cites exact file, "
                            "line range, and supplied snippet"
                        ),
                        "confidence": "number between 0 and 1",
                        "evidence_ids": "array of supplied evidence ids",
                    }
                ]
            },
        }
        try:
            response = self.provider(request, model=self.model)
        except LLMProviderError:
            raise
        except Exception as error:
            raise LLMProviderError("LLM criterion evaluation failed.") from error
        try:
            response = json.loads(response) if isinstance(response, str) else response
        except (TypeError, ValueError, json.JSONDecodeError) as error:
            raise LLMProviderError(
                "LLM returned unreadable criterion results."
            ) from error
        if not isinstance(response, dict) or not isinstance(
            response.get("evaluations"),
            list,
        ):
            raise LLMProviderError(
                "LLM criterion response must include evaluations."
            )

        criteria_by_id = {criterion.pk: criterion for criterion in criteria}
        evidence_by_id = {item.pk: item for item in evidence}
        results = {}
        valid_statuses = {
            "satisfied",
            "partial",
            "missing",
            "not_applicable",
            "failed",
        }
        for item in response["evaluations"]:
            if not isinstance(item, dict):
                raise LLMProviderError("LLM criterion result must be an object.")
            criterion_id = item.get("criterion_id")
            if criterion_id not in criteria_by_id or criterion_id in results:
                raise LLMProviderError(
                    "LLM returned an unknown or duplicate criterion."
                )
            status = item.get("status")
            summary = item.get("summary")
            confidence = item.get("confidence")
            evidence_ids = item.get("evidence_ids")
            if status not in valid_statuses:
                raise LLMProviderError("LLM returned an invalid criterion status.")
            if not isinstance(summary, str):
                raise LLMProviderError("LLM criterion summary must be a string.")
            if (
                isinstance(confidence, bool)
                or not isinstance(confidence, (int, float))
                or not 0 <= confidence <= 1
            ):
                raise LLMProviderError(
                    "LLM criterion confidence must be between 0 and 1."
                )
            if not isinstance(evidence_ids, list):
                raise LLMProviderError(
                    "LLM criterion result must include evidence_ids."
                )
            try:
                supporting_evidence = [
                    evidence_by_id[evidence_id]
                    for evidence_id in evidence_ids
                ]
            except KeyError as error:
                raise LLMProviderError(
                    "LLM referenced evidence outside the supplied collection."
                ) from error
            if status == "satisfied" and not supporting_evidence:
                raise LLMProviderError(
                    "LLM cannot satisfy a criterion without supporting evidence."
                )
            results[criterion_id] = {
                "status": status,
                "summary": summary,
                "confidence": confidence,
                "evidence": supporting_evidence,
            }

        if set(results) != set(criteria_by_id):
            raise LLMProviderError(
                "LLM did not return a result for every criterion."
            )
        return results