"""Deterministic, explainable delivery decisions for completed verifications."""

from django.db import transaction
from django.utils import timezone

from Requora_backend.RequoraApp.models import (
    CriterionVerification,
    DeliveryDecision,
    RequirementCriterion,
    Verification,
)


FINAL_DECISION_STATUSES = {"verified", "partial", "unverified", "failed"}


def _latest_criterion_results(verification):
    """Return the most recent evaluation for every criterion in a verification."""

    results = CriterionVerification.objects.filter(
        verification=verification,
    ).order_by("criterion_id", "-evaluated_at", "-id")
    latest_results = {}
    for result in results:
        latest_results.setdefault(result.criterion_id, result)
    return latest_results


def evaluate_delivery_decision(*, verification):
    """Derive a conservative decision and structured rationale without AI."""

    if verification.status == "stale":
        return "stale", "The underlying verification is stale.", {}
    if verification.status == "failed":
        return "failed", "The underlying verification failed.", {}
    if verification.status == "pending":
        return "unverified", "The underlying verification is pending.", {}

    required_criteria = RequirementCriterion.objects.filter(
        requirement=verification.requirement,
        is_active=True,
        required=True,
    ).order_by("order", "id")
    latest_results = _latest_criterion_results(verification)
    missing = []
    partial = []

    for criterion in required_criteria:
        result = latest_results.get(criterion.id)
        if result is None or result.status in {"pending", "missing", "failed"}:
            missing.append({"id": criterion.id, "text": criterion.text})
        elif result.status == "partial":
            partial.append({"id": criterion.id, "text": criterion.text})

    rationale = {
        "required_criteria_count": required_criteria.count(),
        "missing_required_criteria": missing,
        "partial_required_criteria": partial,
    }
    if missing:
        return "unverified", "Required criteria are missing.", rationale
    if partial:
        return "partial", "Required criteria are only partially satisfied.", rationale

    # Never strengthen the established verification conclusion. Criteria add
    # semantic detail; they do not make missing code, test, or CI evidence OK.
    if verification.status == "verified":
        return "verified", "All required criteria are satisfied.", rationale
    return "partial", verification.summary or "Verification is partial.", rationale


@transaction.atomic
def create_delivery_decision(*, verification):
    """Persist a new current decision and retain older snapshots for audit."""

    verification = Verification.objects.select_for_update().get(pk=verification.pk)
    status, summary, rationale = evaluate_delivery_decision(verification=verification)
    now = timezone.now()
    DeliveryDecision.objects.filter(
        verification=verification,
        is_current=True,
    ).update(is_current=False, superseded_at=now)

    return DeliveryDecision.objects.create(
        verification=verification,
        status=status,
        summary=summary,
        confidence=verification.confidence,
        rationale=rationale,
    )


def get_current_delivery_decision(*, verification):
    return DeliveryDecision.objects.filter(
        verification=verification,
        is_current=True,
    ).first()
