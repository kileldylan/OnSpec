from django.db import transaction
from django.utils import timezone

from Requora_backend.RequoraApp.models import (
    Evidence,
    PullRequest,
    Requirement,
    Verification,
    VerificationEvidence,
)


VALID_VERIFICATION_STATUSES = {
    "pending",
    "verified",
    "partial",
    "unverified",
    "stale",
    "failed",
}


@transaction.atomic
def create_verification(
    *,
    requirement,
    pull_request,
    status,
    summary="",
    confidence=None,
    evidence=None,
):
    """
    Create a verification result for a requirement against a pull request.

    A verification represents Requora's current conclusion about whether
    a particular requirement has been satisfied by a pull request.

    Evidence provides the supporting implementation facts behind
    that conclusion.
    """

    if status not in VALID_VERIFICATION_STATUSES:
        raise ValueError(
            f"Invalid verification status: {status}"
        )

    if confidence is not None:
        if confidence < 0 or confidence > 1:
            raise ValueError(
                "Confidence must be between 0 and 1."
            )

    if evidence is None:
        evidence = []

    verification = Verification.objects.create(
        requirement=requirement,
        pull_request=pull_request,
        status=status,
        summary=summary,
        confidence=confidence,
        verified_at=timezone.now(),
    )

    VerificationEvidence.objects.bulk_create(
        [
            VerificationEvidence(
                verification=verification,
                evidence=evidence_item,
            )
            for evidence_item in evidence
        ]
    )

    return verification