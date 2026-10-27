"""Deterministic persistence helpers for requirement verification criteria."""

import ast
from fnmatch import fnmatch
import html
import json
import re

from django.db import transaction
from django.db.models import Max

from ACI_backend.ACIApp.models import (
    CriterionVerification,
    CriterionVerificationEvidence,
    Evidence,
    RequirementCriterion,
    Verification,
    VerificationEvidence,
)


CRITERION_VERIFICATION_STATUSES = {
    "pending",
    "satisfied",
    "partial",
    "missing",
    "not_applicable",
    "failed",
}


DEFAULT_EVIDENCE_TYPES = {
    "behavior": {"code", "runtime", "test"},
    "implementation": {"code"},
    "test": {"test"},
    "integration": {"code", "test", "ci"},
    "data": {"code", "test"},
    "security": {"code", "test", "ci"},
    "configuration": {"code", "ci"},
}


def list_active_criteria(*, requirement):
    """Return active criteria for a requirement, ordered for evaluation."""
    return RequirementCriterion.objects.filter(
        requirement=requirement,
        is_active=True,
    ).order_by("order", "id")


def create_criterion(
    *,
    requirement,
    text,
    category="behavior",
    expectations=None,
    priority=0,
    required=True,
):
    """Create a new criterion for a requirement."""
    if expectations is None:
        expectations = {}

    max_order = (
        RequirementCriterion.objects.filter(requirement=requirement)
        .aggregate(max_order=Max("order"))["max_order"]
    )
    order = (max_order + 1) if max_order is not None else 0

    return RequirementCriterion.objects.create(
        requirement=requirement,
        text=text,
        category=category,
        expectations=expectations,
        priority=priority,
        required=required,
        order=order,
    )


def update_criterion(*, criterion, **fields):
    """Update fields on an existing criterion."""
    for key, value in fields.items():
        setattr(criterion, key, value)
    criterion.save()
    return criterion


def deactivate_criterion(*, criterion):
    """Deactivate a criterion (soft delete)."""
    criterion.is_active = False
    criterion.save(update_fields=["is_active", "updated_at"])
    return criterion


def generate_initial_criteria(*, requirement, criteria):
    """Bulk create initial criteria from a list of dicts."""
    created = []
    for crit in criteria:
        c = create_criterion(
            requirement=requirement,
            text=crit["text"],
            category=crit.get("category", "behavior"),
            expectations=crit.get("expectations"),
        )
        created.append(c)
    return created


def _normalize_jira_text(value):
    """Coerce Jira rich-text objects into plain text."""
    if value is None:
        return ""

    if isinstance(value, str):
        text = value.strip()
        if text.startswith("{") or text.startswith("["):
            for parser in (json.loads, ast.literal_eval):
                try:
                    return _normalize_jira_text(parser(text))
                except (TypeError, ValueError, SyntaxError):
                    continue
    elif isinstance(value, (list, tuple)):
        text = "\n".join(
            part for part in (_normalize_jira_text(item) for item in value) if part
        )
        return text.strip()
    elif isinstance(value, dict):
        node_type = value.get("type")
        if node_type in {"bulletList", "orderedList"}:
            return "\n".join(
                part for part in (
                    _normalize_jira_text(item) for item in value.get("content", [])
                ) if part
            )
        if node_type == "listItem":
            return "\n".join(
                part for part in (
                    _normalize_jira_text(item) for item in value.get("content", [])
                ) if part
            )
        if node_type == "paragraph":
            return _normalize_jira_text(value.get("content", []))
        if isinstance(value.get("text"), str):
            return value["text"]
        if isinstance(value.get("value"), str):
            return value["value"]
        if "content" in value:
            return _normalize_jira_text(value["content"])
        chunks = []
        for key, item in value.items():
            if key in {"type", "attrs", "attributes", "marks"}:
                continue
            chunk = _normalize_jira_text(item)
            if chunk:
                chunks.append(chunk)
        return "\n".join(chunks).strip()
    else:
        text = str(value)

    text = html.unescape(text)
    text = re.sub(r"<[^>]+>", "\n", text)
    text = text.replace("\r\n", "\n").replace("\r", "\n")
    return text.strip()


def _looks_like_raw_jira_blob(value):
    text = (value or "").strip()
    if not text:
        return False
    if text.startswith("{") or text.startswith("["):
        return True
    return any(
        marker in text.lower()
        for marker in (
            "'type':",
            "'content':",
            "localid",
            "attrs",
            "orderedlist",
            "bulletlist",
            "listitem",
        )
    )


def _criterion_identity(value):
    text = (value or "").strip()
    text = text.lower()
    text = text.replace("/", "")
    text = re.sub(r"\s+", " ", text)
    text = re.sub(r"[^a-z0-9 ]+", "", text)
    return text.strip()


def sync_requirement_criteria_from_text(*, requirement, text=None):
    """Create or refresh active criteria from a requirement description."""
    raw_text = _normalize_jira_text(
        text if text is not None else requirement.description or "",
    )
    if not raw_text:
        return []

    stale_criteria = RequirementCriterion.objects.filter(
        requirement=requirement,
        is_active=True,
    ).exclude(text="")
    for criterion in list(stale_criteria):
        if _looks_like_raw_jira_blob(criterion.text):
            criterion.delete()

    lines = []
    criteria_marker = None
    lowered = raw_text.lower()
    for marker in ("acceptance criteria", "criteria"):
        idx = lowered.find(marker)
        if idx != -1:
            criteria_marker = marker
            remainder = raw_text[idx + len(marker):]
            remainder = remainder.lstrip(" :;\t\n-")
            if "\n" in remainder:
                lines = [
                    part.strip() for part in remainder.splitlines()
                    if part and part.strip()
                ]
            else:
                remainder = re.sub(r"\s+", " ", remainder)
                parts = re.split(
                    r"(?:^|(?<=\s))\d+\.?\s+(?=[A-Z])|(?:^|(?<=\s))[-*•]\s+",
                    remainder,
                )
                lines = [part.strip() for part in parts if part and part.strip()]
            break

    if not lines:
        in_criteria_block = False
        for raw_line in raw_text.splitlines():
            line = raw_line.strip()
            if not line:
                continue
            normalized = line.lower()
            if "acceptance criteria" in normalized or normalized == "criteria":
                in_criteria_block = True
                continue
            if normalized.startswith(("definition of done", "notes:", "notes")):
                if in_criteria_block:
                    break
                continue
            cleaned = re.sub(r"^(?:[-*•]|\d+[.)])\s*", "", line)
            cleaned = cleaned.strip()
            if not cleaned:
                continue
            if in_criteria_block or (len(raw_text.splitlines()) <= 3 and re.match(r"^(?:[-*•]|\d+[.)])\s*", line)):
                lines.append(cleaned)

    if not lines:
        fallback_lines = []
        for raw_line in raw_text.splitlines():
            line = raw_line.strip()
            if not line:
                continue
            if re.match(r"^(?:[-*•]|\d+[.)])\s*", line):
                cleaned = re.sub(r"^(?:[-*•]|\d+[.)])\s*", "", line).strip()
                if cleaned:
                    fallback_lines.append(cleaned)
        if fallback_lines:
            lines = fallback_lines
        else:
            lines = [raw_text[:220].strip()]

    existing = {
        _criterion_identity(item.text): item
        for item in RequirementCriterion.objects.filter(
            requirement=requirement,
            is_active=True,
        )
    }

    duplicates = []
    seen = set()
    for item in RequirementCriterion.objects.filter(
        requirement=requirement,
        is_active=True,
    ).order_by("order", "id"):
        key = _criterion_identity(item.text)
        if not key:
            continue
        if key in seen:
            duplicates.append(item)
            continue
        seen.add(key)

    for item in duplicates:
        item.delete()

    created = []
    for text_value in lines[:12]:
        candidate = text_value.strip()
        if not candidate or candidate.lower() in {"acceptance criteria", "criteria"}:
            continue
        normalized_candidate = _criterion_identity(candidate)
        if normalized_candidate in existing:
            continue
        created.append(create_criterion(
            requirement=requirement,
            text=candidate,
            category="behavior",
            required=True,
        ))
        existing[normalized_candidate] = created[-1]
    return created


@transaction.atomic
def record_criterion_verification(
    *,
    verification,
    criterion,
    status,
    summary="",
    confidence=None,
    metadata=None,
    evidence=None,
):
    """Persist a criterion evaluation result and link supporting evidence."""
    if metadata is None:
        metadata = {}
    if evidence is None:
        evidence = []

    cv = CriterionVerification.objects.create(
        verification=verification,
        criterion=criterion,
        status=status,
        summary=summary,
        confidence=confidence,
        metadata=metadata,
    )

    for ev in evidence:
        CriterionVerificationEvidence.objects.get_or_create(
            criterion_verification=cv,
            evidence=ev,
        )
        VerificationEvidence.objects.get_or_create(
            verification=verification,
            evidence=ev,
        )

    return cv


def _expected_evidence_types(criterion):
    expectations = criterion.expectations or {}
    expected_types = expectations.get("evidence_types")
    if expected_types is None and expectations.get("evidence_type"):
        expected_types = [expectations["evidence_type"]]
    if isinstance(expected_types, str):
        expected_types = [expected_types]
    return set(expected_types or DEFAULT_EVIDENCE_TYPES.get(
        criterion.category,
        {"code"},
    ))


def _source_file_role(evidence_item):
    metadata = evidence_item.metadata or {}
    role = metadata.get("evidence_role")
    if role:
        return role

    filename = metadata.get("filename") or (
        evidence_item.changed_file.filename
        if evidence_item.changed_file_id
        else ""
    )
    normalized = "/" + filename.replace("\\", "/").lower()
    if (
        filename.lower().endswith((".adoc", ".md", ".rst", ".txt"))
        or normalized.startswith("/docs/")
    ):
        return "documentation"
    name = normalized.rsplit("/", 1)[-1]
    if (
        any(marker in normalized for marker in ("/test/", "/tests/", "/__tests__/"))
        or name.startswith("test_")
        or ".test." in name
        or ".spec." in name
    ):
        return "test"
    return "implementation"


def effective_evidence_type(evidence_item):
    """Map changed-file evidence to implementation, test, or no code proof."""
    if evidence_item.evidence_type != "code":
        return evidence_item.evidence_type
    role = _source_file_role(evidence_item)
    if role == "documentation":
        return None
    if role == "test":
        return "test"
    metadata = evidence_item.metadata or {}
    snippet = metadata.get("snippet")
    if not snippet and evidence_item.changed_file_id:
        snippet = evidence_item.changed_file.patch
    return "code" if snippet else None


def _matching_evidence(*, criterion, evidence):
    expectations = criterion.expectations or {}
    expected_types = _expected_evidence_types(criterion)
    path_patterns = expectations.get("path_patterns", [])

    matches = []
    for evidence_item in evidence:
        evidence_type = effective_evidence_type(evidence_item)
        if evidence_type not in expected_types:
            continue
        metadata = evidence_item.metadata or {}
        if evidence_item.evidence_type == "code":
            snippet = metadata.get("snippet")
            if not snippet and evidence_item.changed_file_id:
                snippet = evidence_item.changed_file.patch
            if not snippet:
                continue
            if not _analyze_patch_relevance(
                criterion.text,
                snippet,
            )["relevant"]:
                continue
        if path_patterns:
            filename = (
                evidence_item.changed_file.filename
                if evidence_item.changed_file_id
                else evidence_item.metadata.get("filename", "")
            )
            if not any(fnmatch(filename, pattern) for pattern in path_patterns):
                continue
        matches.append(evidence_item)
    return matches


def _analyze_patch_relevance(criterion_text: str, patch: str) -> dict:
    """
    Simple but effective analysis of whether the patch appears to address the criterion.
    Looks for keywords from the criterion in the added lines.
    """
    if not patch:
        return {"relevant": False, "added_lines": 0, "keywords_found": []}

    criterion_lower = criterion_text.lower()
    keywords = re.findall(r'\b\w{4,}\b', criterion_lower)
    keywords = [k for k in keywords if len(k) > 3][:8]  # limit noise

    patch_lines = patch.splitlines()
    added_lines = []
    for line in patch_lines:
        if line.startswith('+') and not line.startswith('+++'):
            added_lines.append(line[1:].strip())
    if not added_lines and not any(
        line.startswith(("@@", "+++", "---")) for line in patch_lines
    ):
        added_lines = [line.strip() for line in patch_lines if line.strip()]

    added_text = " ".join(added_lines).lower()
    found = [kw for kw in keywords if kw in added_text]

    return {
        "relevant": len(found) > 0,
        "added_lines": len(added_lines),
        "keywords_found": found,
    }


def _build_criterion_summary(criterion, valid_evidence, invalid_evidence):
    """Generate a precise, intelligent summary instead of generic text."""
    criterion_text = criterion.text

    if invalid_evidence:
        return f"Evidence for '{criterion_text[:60]}...' was collected but marked invalid."

    if not valid_evidence:
        return f"No evidence found addressing: {criterion_text}"

    relevant_files = []
    for ev in valid_evidence:
        if effective_evidence_type(ev) != "code":
            continue
        metadata = ev.metadata or {}
        filename = metadata.get("filename") or (
            ev.changed_file.filename if ev.changed_file_id else ""
        )
        snippet = metadata.get("snippet") or (
            ev.changed_file.patch if ev.changed_file_id else ""
        )
        analysis = _analyze_patch_relevance(criterion_text, snippet)
        if analysis["relevant"]:
            line_start = metadata.get("line_start")
            line_end = metadata.get("line_end")
            line_label = (
                f":{line_start}-{line_end}"
                if line_start is not None and line_end is not None
                else ""
            )
            relevant_files.append(f"{filename}{line_label}")

    if relevant_files:
        files_str = ", ".join(relevant_files[:3])
        if len(relevant_files) > 3:
            files_str += f" (+{len(relevant_files) - 3} more)"
        return f"Relevant implementation changes in {files_str}."

    # Fallback for non-code evidence
    types = sorted({e.evidence_type for e in valid_evidence})
    return f"Evidence collected ({', '.join(types)}) for criterion: {criterion_text[:70]}..."


@transaction.atomic
def execute_criteria(*, verification, evidence=None, evaluator=None):
    """Evaluate every active criterion against the supplied evidence with precise analysis."""

    if evidence is None:
        evidence = Evidence.objects.filter(
            requirement=verification.requirement,
            pull_request=verification.pull_request,
            status__in=["valid", "invalid"],
        ).select_related("changed_file", "changed_file__commit")
    evidence = list(evidence)
    criteria = list(list_active_criteria(requirement=verification.requirement))
    llm_results = None
    evaluate_criteria = getattr(evaluator, "evaluate_criteria", None)
    if callable(evaluate_criteria) and criteria:
        eligible_evidence = [
            item
            for item in evidence
            if item.status == "valid"
            and effective_evidence_type(item) is not None
        ]
        llm_results = evaluate_criteria(
            verification.requirement,
            criteria,
            eligible_evidence,
        )

    results = []

    for criterion in criteria:
        if llm_results is not None:
            result = llm_results[criterion.pk]
            results.append(record_criterion_verification(
                verification=verification,
                criterion=criterion,
                status=result["status"],
                summary=result["summary"],
                confidence=result["confidence"],
                metadata={
                    "evidence_types": sorted(
                        _expected_evidence_types(criterion),
                    ),
                    "evidence_count": len(result["evidence"]),
                    "evaluator": "llm",
                },
                evidence=result["evidence"],
            ))
            continue

        valid_evidence = _matching_evidence(
            criterion=criterion,
            evidence=[item for item in evidence if item.status == "valid"],
        )
        invalid_evidence = _matching_evidence(
            criterion=criterion,
            evidence=[item for item in evidence if item.status == "invalid"],
        )

        if invalid_evidence:
            status = "failed"
            summary = _build_criterion_summary(criterion, [], invalid_evidence)
            confidence = 0.0
            supporting_evidence = invalid_evidence
        elif valid_evidence:
            # More intelligent status determination
            has_code = any(e.evidence_type == "code" for e in valid_evidence)
            has_test = any(e.evidence_type == "test" for e in valid_evidence)

            if criterion.category in ("test", "security") and not has_test:
                status = "partial"
                confidence = 0.6
            elif has_code:
                status = "satisfied"
                confidence = 0.85
            else:
                status = "satisfied"
                confidence = 0.7

            summary = _build_criterion_summary(criterion, valid_evidence, [])
            supporting_evidence = valid_evidence
        else:
            status = "missing"
            summary = _build_criterion_summary(criterion, [], [])
            confidence = 0.0
            supporting_evidence = []

        results.append(record_criterion_verification(
            verification=verification,
            criterion=criterion,
            status=status,
            summary=summary,
            confidence=confidence,
            metadata={
                "evidence_types": sorted(
                    _expected_evidence_types(criterion),
                ),
                "evidence_count": len(supporting_evidence),
            },
            evidence=supporting_evidence,
        ))
    return results
