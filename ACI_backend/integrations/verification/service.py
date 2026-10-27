from datetime import timedelta
import logging
import re
from urllib.parse import quote

from django.conf import settings
from django.db import transaction
from django.utils import timezone

from ACI_backend.ACIApp.models import (
    ChangedFile,
    Commit,
    CriterionVerification,
    DeliveryDecision,
    Evidence,
    EvidenceInvalidation,
    PullRequest,
    Requirement,
    Verification,
    VerificationEvidence,
    VerificationRun,
)
from ACI_backend.integrations.verification.criteria import (
    effective_evidence_type,
    execute_criteria,
    list_active_criteria,
)
from ACI_backend.integrations.github.client import GitHubClient
from ACI_backend.integrations.github.client import GitHubAPIError
from ACI_backend.integrations.verification.decisions import (
    create_delivery_decision,
)
from ACI_backend.integrations.verification.errors import (
    LLMProviderError,
    VerificationProcessingError,
)
from ACI_backend.integrations.verification.execution import execute_test_run


logger = logging.getLogger(__name__)


FINAL_VERIFICATION_STATUSES = {
    "verified",
    "partial",
    "unverified",
    "failed",
}

DEFAULT_GITHUB_TEST_CONTEXTS = {
    "test",
    "tests",
    "pytest",
    "unit",
    "unit-tests",
}
DEFAULT_GITHUB_CI_CONTEXTS = {
    "build",
    "ci",
    "lint",
    "codeql",
    "security",
}

DOCUMENTATION_EXTENSIONS = {".adoc", ".md", ".rst", ".txt"}
TEST_FILE_MARKERS = {"/test/", "/tests/", "/__tests__/"}
SOURCE_EXTENSIONS = {
    ".c", ".cc", ".cpp", ".cs", ".go", ".h", ".hpp", ".java", ".js",
    ".jsx", ".kt", ".php", ".py", ".rb", ".rs", ".scala", ".sql", ".swift",
    ".ts", ".tsx",
}
IGNORED_SOURCE_PATHS = {
    ".git", ".venv", "build", "dist", "migrations", "node_modules",
    "vendor",
}
SOURCE_FILE_SCAN_LIMIT = 12
SOURCE_FILE_MAX_BYTES = 200_000
SOURCE_SNIPPET_MAX_LINES = 20
SOURCE_MATCH_STOPWORDS = {
    "about", "after", "also", "and", "are", "can", "does", "each", "from",
    "have", "into", "must", "that", "the", "their", "then", "there", "this",
    "through", "when", "where", "which", "with", "should",
}


def _changed_file_role(filename):
    normalized = "/" + filename.replace("\\", "/").lower()
    extension = f".{filename.rsplit('.', 1)[-1].lower()}" if "." in filename else ""
    if extension in DOCUMENTATION_EXTENSIONS or normalized.startswith("/docs/"):
        return "documentation"
    name = normalized.rsplit("/", 1)[-1]
    if (
        any(marker in normalized for marker in TEST_FILE_MARKERS)
        or name.startswith("test_")
        or ".test." in name
        or ".spec." in name
    ):
        return "test"
    return "implementation"


def _extract_added_code_snippet(patch, *, max_lines=20):
    """Return added diff lines with their line numbers in the new file."""
    if not patch:
        return {"snippet": "", "line_start": None, "line_end": None}

    new_line = None
    added_lines = []
    for line in patch.splitlines():
        if line.startswith("@@"):
            match = re.match(r"@@ -\d+(?:,\d+)? \+(\d+)(?:,\d+)? @@", line)
            new_line = int(match.group(1)) if match else None
        elif line.startswith("+++") or line.startswith("\\"):
            continue
        elif line.startswith("+"):
            if new_line is not None:
                added_lines.append((new_line, line[1:]))
                new_line += 1
        elif line.startswith("-"):
            continue
        elif new_line is not None:
            new_line += 1

    added_lines = added_lines[:max_lines]
    if not added_lines:
        return {"snippet": "", "line_start": None, "line_end": None}
    return {
        "snippet": "\n".join(content for _, content in added_lines),
        "line_start": added_lines[0][0],
        "line_end": added_lines[-1][0],
    }


def _source_search_terms(requirement, criteria):
    text = " ".join(
        [criterion.text for criterion in criteria]
        + [requirement.title, requirement.description]
    )
    words = re.findall(r"[A-Za-z][A-Za-z0-9]*", re.sub(r"([a-z])([A-Z])", r"\1 \2", text))
    terms = [
        word.lower()
        for word in words
        if len(word) >= 3 and word.lower() not in SOURCE_MATCH_STOPWORDS
    ]
    return set(terms[:30])


def _source_candidate_score(path, search_terms):
    path_terms = set(
        re.findall(r"[A-Za-z][A-Za-z0-9]*", re.sub(r"([a-z])([A-Z])", r"\1 \2", path))
    )
    return len({term.lower() for term in path_terms} & search_terms)


def _is_source_candidate(item):
    path = item.get("path", "")
    parts = {part.lower() for part in path.split("/")}
    extension = "." + path.rsplit(".", 1)[-1].lower() if "." in path else ""
    return (
        item.get("type") == "blob"
        and extension in SOURCE_EXTENSIONS
        and item.get("size", SOURCE_FILE_MAX_BYTES + 1) <= SOURCE_FILE_MAX_BYTES
        and not parts.intersection(IGNORED_SOURCE_PATHS)
        and _changed_file_role(path) == "implementation"
        and not path.lower().endswith((".min.js", ".min.css"))
    )


def _extract_relevant_source_snippet(source, search_terms):
    """Choose one short source window with the strongest literal term match."""
    lines = source.splitlines()
    if not lines or not search_terms:
        return None

    window_matches = {}
    for term in search_terms:
        matcher = re.compile(
            rf"(?<![A-Za-z0-9]){re.escape(term)}(?![A-Za-z0-9])",
            flags=re.IGNORECASE,
        )
        for line_index, line in enumerate(lines):
            if not matcher.search(line):
                continue
            first_start = max(0, line_index - SOURCE_SNIPPET_MAX_LINES + 1)
            for start in range(first_start, line_index + 1):
                window_matches.setdefault(start, set()).add(term)

    if not window_matches:
        return None

    start = max(
        window_matches,
        key=lambda index: (
            len(window_matches[index]),
            -index,
        ),
    )
    end = min(start + SOURCE_SNIPPET_MAX_LINES, len(lines))
    return {
        "snippet": "\n".join(lines[start:end]),
        "line_start": start + 1,
        "line_end": end,
        "matched_terms": sorted(window_matches[start]),
    }


def collect_repository_code_evidence(
    *,
    requirement,
    pull_request,
    github_client=None,
):
    """Find implementation snippets in source files at the PR head commit."""
    criteria = list(list_active_criteria(requirement=requirement))
    search_terms = _source_search_terms(requirement, criteria)
    if not search_terms:
        return []

    github_client = github_client or GitHubClient(
        token=settings.GITHUB_ACCESS_TOKEN,
    )
    tree = github_client.get_repository_tree(
        pull_request.repository.owner,
        pull_request.repository.name,
        pull_request.head_sha,
    )
    candidates = [
        item for item in tree.get("tree", [])
        if _is_source_candidate(item)
    ]
    candidates.sort(
        key=lambda item: (
            -_source_candidate_score(item["path"], search_terms),
            item["path"].count("/"),
            item["path"].lower(),
        )
    )

    commit = Commit.objects.filter(
        repository=pull_request.repository,
        sha=pull_request.head_sha,
    ).first()
    current_evidence = []
    for candidate in candidates[:SOURCE_FILE_SCAN_LIMIT]:
        path = candidate["path"]
        source = github_client.get_repository_file(
            pull_request.repository.owner,
            pull_request.repository.name,
            path,
            pull_request.head_sha,
        )
        snippet_data = _extract_relevant_source_snippet(source, search_terms)
        if snippet_data is None:
            continue

        source_url = (
            f"https://github.com/{pull_request.repository.full_name}/blob/"
            f"{pull_request.head_sha}/{quote(path, safe='/')}"
            f"#L{snippet_data['line_start']}-L{snippet_data['line_end']}"
        )
        metadata = {
            "source": "repository_snapshot",
            "source_sha": pull_request.head_sha,
            "source_path": path,
            "filename": path,
            "evidence_role": "implementation",
            "snippet": snippet_data["snippet"],
            "line_start": snippet_data["line_start"],
            "line_end": snippet_data["line_end"],
            "matched_terms": snippet_data["matched_terms"],
            "source_url": source_url,
        }
        evidence = Evidence.objects.filter(
            requirement=requirement,
            pull_request=pull_request,
            evidence_type="code",
            metadata__source="repository_snapshot",
            metadata__source_path=path,
        ).first()
        if evidence is None:
            evidence = Evidence.objects.create(
                requirement=requirement,
                pull_request=pull_request,
                commit=commit,
                evidence_type="code",
                status="valid",
                description=f"Implementation source: {path}",
                metadata=metadata,
            )
        else:
            evidence.commit = commit
            evidence.status = "valid"
            evidence.description = f"Implementation source: {path}"
            evidence.metadata = metadata
            evidence.save(
                update_fields=[
                    "commit",
                    "status",
                    "description",
                    "metadata",
                    "updated_at",
                ]
            )
        current_evidence.append(evidence)

    Evidence.objects.filter(
        requirement=requirement,
        pull_request=pull_request,
        evidence_type="code",
        status="valid",
        metadata__source="repository_snapshot",
    ).exclude(metadata__source_sha=pull_request.head_sha).update(
        status="stale",
        updated_at=timezone.now(),
    )
    return current_evidence


def classify_github_context(context):
    """Map a GitHub check/status context to an evidence type explicitly."""

    normalized = (context or "").strip().lower()
    test_contexts = {
        item.strip().lower()
        for item in getattr(
            settings,
            "GITHUB_TEST_EVIDENCE_CONTEXTS",
            DEFAULT_GITHUB_TEST_CONTEXTS,
        )
    }
    ci_contexts = {
        item.strip().lower()
        for item in getattr(
            settings,
            "GITHUB_CI_EVIDENCE_CONTEXTS",
            DEFAULT_GITHUB_CI_CONTEXTS,
        )
    }
    if normalized in test_contexts:
        return "test"
    if normalized in ci_contexts:
        return "ci"
    return None


def validate_evaluator_conclusion(*, requirement, evidence, conclusion):
    """Validate an evaluator result before it can affect durable state."""

    required_fields = {"status", "summary", "confidence", "evidence"}
    missing_fields = required_fields - set(conclusion)
    if missing_fields:
        raise ValueError(
            "Evaluator conclusion is missing: "
            + ", ".join(sorted(missing_fields))
        )

    if conclusion["status"] not in FINAL_VERIFICATION_STATUSES:
        raise ValueError("Evaluator returned an invalid status.")
    confidence = conclusion["confidence"]
    if isinstance(confidence, bool) or not isinstance(confidence, (int, float)):
        raise ValueError("Evaluator confidence must be numeric.")
    if not 0 <= confidence <= 1:
        raise ValueError("Evaluator confidence must be between 0 and 1.")
    if not isinstance(conclusion["summary"], str):
        raise ValueError("Evaluator summary must be a string.")
    evidence_list = conclusion["evidence"]
    if isinstance(evidence_list, (str, bytes)) or not hasattr(evidence_list, "__iter__"):
        raise ValueError("Evaluator evidence must be a list.")
    evidence_list = list(evidence_list)
    conclusion["evidence"] = evidence_list

    supplied_evidence = {item.pk: item for item in evidence}
    for item in evidence_list:
        if item.pk not in supplied_evidence:
            raise ValueError("Evaluator referenced evidence outside its input.")
        if item.requirement_id != requirement.pk:
            raise ValueError("Evaluator evidence belongs to another requirement.")
        if item.status == "stale":
            raise ValueError("Evaluator cannot reference stale evidence.")
        if item.status == "invalid" and conclusion["status"] != "failed":
            raise ValueError(
                "Invalid evidence may only support a failed conclusion."
            )

    return conclusion


def _get_changed_filenames(evidence):
    """Extract unique filenames from implementation evidence."""
    filenames = set()
    for item in evidence:
        if effective_evidence_type(item) != "code":
            continue
        if item.changed_file and item.changed_file.filename:
            filenames.add(item.changed_file.filename)
        elif item.metadata and item.metadata.get("filename"):
            filenames.add(item.metadata["filename"])
    return sorted(filenames)


def _get_evidence_labels(evidence, ev_type):
    """Extract human readable names for test or CI evidence."""
    labels = []
    for item in evidence:
        if item.evidence_type != ev_type:
            continue
        name = (
            item.metadata.get("name")
            or item.metadata.get("context")
            or item.description
        )
        if name:
            labels.append(str(name))
    return labels


def _build_evidence_summary(pull_request, valid_evidence, missing_types=None):
    """Create a specific, informative summary based on actual evidence."""
    pr_num = pull_request.number
    code_files = _get_changed_filenames(valid_evidence)

    file_part = ""
    if code_files:
        shown = ", ".join(code_files[:4])
        if len(code_files) > 4:
            shown += f" (+{len(code_files) - 4} more)"
        file_part = f" Changes in {len(code_files)} files: {shown}."

    if missing_types:
        labels = {"test": "test", "ci": "CI"}
        missing = " and ".join(labels.get(t, t) for t in sorted(missing_types))
        return (
            f"Code evidence collected for PR #{pr_num}.{file_part} "
            f"Missing valid {missing} evidence."
        )

    # Verified case
    test_names = _get_evidence_labels(valid_evidence, "test")
    ci_names = _get_evidence_labels(valid_evidence, "ci")

    extra = ""
    if test_names or ci_names:
        parts = []
        if test_names:
            parts.append(f"tests: {', '.join(test_names[:2])}")
        if ci_names:
            parts.append(f"CI: {', '.join(ci_names[:2])}")
        extra = " (" + "; ".join(parts) + ")"

    return (
        f"PR #{pr_num} has valid code, test, and CI evidence.{file_part}{extra}"
    )


def _criteria_outcome_for_verification(verification):
    """Score verification quality using the requirement's acceptance criteria."""
    results = list(
        CriterionVerification.objects.filter(verification=verification)
        .select_related("criterion")
        .order_by("criterion__order", "criterion_id", "evaluated_at", "id")
    )
    if not results:
        return None

    total = len(results)
    satisfied = sum(1 for result in results if result.status == "satisfied")
    partial = sum(1 for result in results if result.status == "partial")
    failed = sum(1 for result in results if result.status in {"failed", "missing"})
    not_applicable = sum(1 for result in results if result.status == "not_applicable")
    active_total = total - not_applicable
    if active_total == 0:
        return {
            "status": "verified",
            "summary": "All applicable acceptance criteria were marked not applicable.",
            "confidence": 1.0,
        }

    ratio = satisfied / active_total
    if failed and satisfied == 0 and partial == 0:
        status = "unverified"
    elif failed or partial:
        status = "partial"
    elif satisfied == active_total:
        status = "verified"
    else:
        status = "partial"

    confidence = max(0.0, round(ratio, 2))
    summary = (
        f"{satisfied}/{active_total} acceptance criteria satisfied; "
        f"{partial} partial; {failed} missing/failed."
    )
    return {
        "status": status,
        "summary": summary,
        "confidence": confidence,
    }


def _evaluate_evidence(*, requirement, pull_request, evidence):
    """Apply the deterministic policy to an evidence collection.

    Produces more specific summaries that mention actual changed files
    and evidence sources instead of generic templates.
    """

    evidence = list(evidence)
    valid_evidence = [item for item in evidence if item.status == "valid"]
    failed_evidence = [
        item
        for item in evidence
        if (
            item.status == "invalid"
            and item.evidence_type in {"test", "ci"}
            and item.metadata.get("source") == "github"
            and item.metadata.get("head_sha") == pull_request.head_sha
        )
    ]
    evidence_types = {effective_evidence_type(item) for item in valid_evidence}
    evidence_types.discard(None)

    if failed_evidence:
        names = _get_evidence_labels(failed_evidence, "test") + _get_evidence_labels(failed_evidence, "ci")
        name_part = f" ({names[0]})" if names else ""
        return {
            "status": "failed",
            "summary": (
                f"A test or CI check failed for the current head of PR "
                f"#{pull_request.number}{name_part}."
            ),
            "confidence": 0.0,
            "evidence": valid_evidence + failed_evidence,
        }

    if "code" not in evidence_types:
        return {
            "status": "unverified",
            "summary": (
                f"No valid code evidence is available for PR "
                f"#{pull_request.number}."
            ),
            "confidence": 0.0,
            "evidence": valid_evidence,
        }

    required_types = {"code", "test", "ci"}
    missing_types = required_types - evidence_types
    if missing_types:
        summary = _build_evidence_summary(
            pull_request, valid_evidence, missing_types=missing_types
        )
        return {
            "status": "partial",
            "summary": summary,
            "confidence": 0.55,
            "evidence": valid_evidence,
        }

    summary = _build_evidence_summary(pull_request, valid_evidence)
    return {
        "status": "verified",
        "summary": summary,
        "confidence": 0.9,
        "evidence": valid_evidence,
    }


def evaluate(requirement, evidence):
    """Evaluate supplied evidence through ACI's stable evaluator contract."""

    evidence = list(evidence)
    pull_request = next(
        (item.pull_request for item in evidence if item.pull_request_id),
        None,
    )
    if pull_request is None:
        conclusion = {
            "status": "unverified",
            "summary": "No pull request is associated with the evidence.",
            "confidence": 0.0,
            "evidence": [],
        }
        return validate_evaluator_conclusion(
            requirement=requirement,
            evidence=evidence,
            conclusion=conclusion,
        )
    conclusion = _evaluate_evidence(
        requirement=requirement,
        pull_request=pull_request,
        evidence=evidence,
    )
    return validate_evaluator_conclusion(
        requirement=requirement,
        evidence=evidence,
        conclusion=conclusion,
    )


def evaluate_reverification_evidence(*, requirement, pull_request):
    """Evaluate current persisted evidence for a requirement and pull request."""

    evidence = Evidence.objects.filter(
        requirement=requirement,
        pull_request=pull_request,
        status__in=["valid", "invalid"],
    ).order_by("id")
    return _evaluate_evidence(
        requirement=requirement,
        pull_request=pull_request,
        evidence=evidence,
    )


def _build_criteria_summary(verification):
    """Create a short summary of criterion evaluation results."""
    cvs = list(
        CriterionVerification.objects.filter(verification=verification)
        .select_related("criterion")
        .order_by("criterion__order")
    )
    if not cvs:
        return ""

    satisfied = sum(1 for c in cvs if c.status == "satisfied")
    partial = sum(1 for c in cvs if c.status == "partial")
    missing = sum(1 for c in cvs if c.status == "missing")
    failed = sum(1 for c in cvs if c.status == "failed")

    total = len(cvs)
    parts = []
    if satisfied:
        parts.append(f"{satisfied} satisfied")
    if partial:
        parts.append(f"{partial} partial")
    if missing:
        parts.append(f"{missing} missing")
    if failed:
        parts.append(f"{failed} failed")

    detail = "; ".join(parts)
    return f" Criteria status: {detail} ({total} total)."


def ingest_changed_file_evidence(
    requirement,
    pull_request,
):
    """
    Create Evidence records for changed files associated
    with a pull request.

    Each changed file is retained as evidence, but only source changes with
    an added-code snippet can support an implementation claim.
    """

    changed_files = (
        ChangedFile.objects.filter(
            commit__repository=pull_request.repository,
            commit__pull_request=pull_request,
        )
        .select_related("commit")
    )

    evidence_records = []

    for changed_file in changed_files:
        role = _changed_file_role(changed_file.filename)
        snippet_data = (
            _extract_added_code_snippet(changed_file.patch)
            if role in {"implementation", "test"}
            else {"snippet": "", "line_start": None, "line_end": None}
        )
        metadata = {
            "filename": changed_file.filename,
            "status": changed_file.status,
            "additions": changed_file.additions,
            "deletions": changed_file.deletions,
            "changes": changed_file.changes,
            "evidence_role": role,
            **snippet_data,
        }
        if snippet_data["snippet"]:
            metadata["source_url"] = (
                f"https://github.com/{pull_request.repository.full_name}/blob/"
                f"{changed_file.commit.sha}/"
                f"{quote(changed_file.filename, safe='/')}"
                f"#L{snippet_data['line_start']}-L{snippet_data['line_end']}"
            )

        evidence, created = Evidence.objects.get_or_create(
            requirement=requirement,
            pull_request=pull_request,
            commit=changed_file.commit,
            changed_file=changed_file,
            evidence_type="code",
            defaults={
                "status": "valid",
                "description": f"Changed file: {changed_file.filename}",
                "metadata": metadata,
            },
        )

        if not created and evidence.status == "valid":
            evidence.description = f"Changed file: {changed_file.filename}"
            evidence.metadata = metadata
            evidence.save(update_fields=["description", "metadata", "updated_at"])

        evidence_records.append(evidence)

    return evidence_records


def ingest_github_evidence(*, pull_request, commit, event, payload):
    """Persist deterministic test or CI evidence from a GitHub event."""

    if event == "check_run":
        check_run = payload["check_run"]
        name = check_run.get("name", "")
        evidence_type = classify_github_context(name)
        if evidence_type is None:
            return []
        external_key = f"check_run:{name}"
        conclusion = check_run.get("conclusion") or check_run.get("status", "")
        evidence_status = "valid" if conclusion == "success" else "invalid"
        description = f"GitHub check {name or 'unnamed'} concluded {conclusion}."
        metadata = {
            "source": "github",
            "event": event,
            "external_key": external_key,
            "name": name,
            "status": check_run.get("status", ""),
            "conclusion": check_run.get("conclusion"),
            "url": check_run.get("html_url", ""),
            "head_sha": commit.sha,
        }
    elif event == "status":
        context = payload["context"]
        external_key = f"status:{context}"
        state = payload.get("state", "")
        evidence_status = "valid" if state == "success" else "invalid"
        evidence_type = classify_github_context(context)
        if evidence_type is None:
            return []
        description = f"GitHub status {context} is {state}."
        metadata = {
            "source": "github",
            "event": event,
            "external_key": external_key,
            "context": context,
            "state": state,
            "target_url": payload.get("target_url", ""),
            "head_sha": commit.sha,
        }
    else:
        raise ValueError(f"Unsupported GitHub evidence event: {event}")

    evidence_records = []
    requirement_ids = pull_request.requirement_links.values_list(
        "requirement", flat=True,
    )
    for requirement_id in requirement_ids:
        prior_evidence = Evidence.objects.filter(
            requirement_id=requirement_id,
            pull_request=pull_request,
            evidence_type=evidence_type,
            metadata__external_key=external_key,
            status="valid",
        ).exclude(commit=commit)
        for evidence in prior_evidence:
            _invalidate_evidence(evidence, triggering_commit=commit)

        evidence, _ = Evidence.objects.update_or_create(
            requirement_id=requirement_id,
            pull_request=pull_request,
            commit=commit,
            evidence_type=evidence_type,
            metadata__external_key=external_key,
            defaults={
                "status": evidence_status,
                "description": description,
                "metadata": metadata,
            },
        )
        evidence_records.append(evidence)

    return evidence_records


def _invalidate_evidence(evidence, *, triggering_commit):
    """Mark non-file evidence stale and queue affected verifications."""

    evidence.status = "stale"
    evidence.save(update_fields=["status", "updated_at"])
    affected_verifications = Verification.objects.filter(
        evidence_links__evidence=evidence,
    ).distinct()
    stale_at = timezone.now()
    affected_verifications.exclude(status="stale").update(
        status="stale",
        invalidated_at=stale_at,
    )
    DeliveryDecision.objects.filter(
        verification__in=affected_verifications,
        is_current=True,
    ).exclude(status="stale").update(
        status="stale",
        invalidated_at=stale_at,
    )
    triggering_file = triggering_commit.changed_files.order_by("id").first()
    if triggering_file is not None:
        for verification in affected_verifications:
            queue_reverification(
                verification=verification,
                triggering_changed_file=triggering_file,
                reason=f"A newer GitHub result arrived for {triggering_commit.sha}.",
            )


def create_verification(
    requirement,
    pull_request,
):
    """
    Create or retrieve the verification for a requirement
    and pull request.

    A requirement should have at most one active verification
    for a given pull request.
    """

    verification, _ = Verification.objects.get_or_create(
        requirement=requirement,
        pull_request=pull_request,
        defaults={
            "status": "pending",
        },
    )

    return verification


@transaction.atomic
def start_initial_verification(*, requirement, pull_request):
    """Create a verification and queue its first evidence evaluation."""

    verification = create_verification(
        requirement=requirement,
        pull_request=pull_request,
    )
    active_run = VerificationRun.objects.filter(
        verification=verification,
        status__in=["queued", "running"],
    ).first()
    if active_run is not None:
        return verification, active_run

    triggering_changed_file = (
        ChangedFile.objects.filter(
            commit__pull_request=pull_request,
        )
        .select_related("commit")
        .order_by("-commit__committed_at", "-id")
        .first()
    )
    if triggering_changed_file is None:
        raise ValueError(
            "The pull request has no changed files to verify yet."
        )

    run = VerificationRun.objects.create(
        verification=verification,
        triggering_changed_file=triggering_changed_file,
        reason=f"Initial verification for PR #{pull_request.number}.",
    )
    return verification, run


@transaction.atomic
def invalidate_evidence_for_changed_file(changed_file):
    """Invalidate prior code evidence affected by a changed file.

    A code-evidence item is tied to an exact file revision. When a later
    revision of the same repository path arrives, that item is no longer
    current. The resulting invalidation is retained for auditability and any
    verification that relied on the evidence is marked stale.

    Reprocessing the same webhook is safe: the invalidation event is unique
    per evidence item and triggering changed file.
    """

    prior_evidence = (
        Evidence.objects.filter(
            evidence_type="code",
            status="valid",
            changed_file__commit__repository=changed_file.commit.repository,
            changed_file__filename=changed_file.filename,
        )
        .exclude(changed_file=changed_file)
        .select_related("changed_file")
    )

    invalidated_evidence_ids = []
    triggering_pull_request = changed_file.commit.pull_request
    if triggering_pull_request is None:
        reason = f"A newer revision changed {changed_file.filename}."
    else:
        reason = (
            f"PR #{triggering_pull_request.number} changed "
            f"{changed_file.filename}."
        )

    for evidence in prior_evidence:
        EvidenceInvalidation.objects.get_or_create(
            evidence=evidence,
            triggering_changed_file=changed_file,
            defaults={
                "reason": reason,
            },
        )
        evidence.status = "stale"
        evidence.save(update_fields=["status", "updated_at"])
        invalidated_evidence_ids.append(evidence.id)

    if invalidated_evidence_ids:
        stale_at = timezone.now()
        affected_verifications = Verification.objects.filter(
            evidence_links__evidence_id__in=invalidated_evidence_ids,
        ).distinct()

        affected_verifications.exclude(status="stale").update(
            status="stale",
            invalidated_at=stale_at,
        )
        DeliveryDecision.objects.filter(
            verification__in=affected_verifications,
            is_current=True,
        ).exclude(status="stale").update(
            status="stale",
            invalidated_at=stale_at,
        )

        for verification in affected_verifications:
            queue_reverification(
                verification=verification,
                triggering_changed_file=changed_file,
                reason=reason,
            )

    return EvidenceInvalidation.objects.filter(
        triggering_changed_file=changed_file,
        evidence_id__in=invalidated_evidence_ids,
    ).select_related("evidence", "triggering_changed_file")


@transaction.atomic
def queue_reverification(*, verification, triggering_changed_file, reason):
    """Queue one active re-verification run for a stale verification.

    Further changes can add more stale evidence while a run is queued or
    running, but they do not create duplicate work. Once that run reaches a
    terminal state, a future invalidation may queue the next run.
    """

    verification = Verification.objects.select_for_update().get(
        pk=verification.pk,
    )
    active_run = VerificationRun.objects.filter(
        verification=verification,
        status__in=["queued", "running"],
    ).first()

    if active_run is not None:
        return active_run

    return VerificationRun.objects.create(
        verification=verification,
        triggering_changed_file=triggering_changed_file,
        reason=reason,
    )


@transaction.atomic
def claim_reverification_run(*, run_id):
    """Claim a queued run for a worker without processing it twice."""

    run = VerificationRun.objects.select_for_update().get(pk=run_id)

    if run.status != "queued":
        return None

    run.status = "running"
    run.started_at = timezone.now()
    run.save(update_fields=["status", "started_at"])
    return run


@transaction.atomic
def recover_stuck_reverification_runs(*, timeout=timedelta(hours=1), now=None):
    """Fail runs left running after a worker stopped responding."""

    now = now or timezone.now()
    cutoff = now - timeout
    stuck_runs = list(
        VerificationRun.objects.select_for_update().filter(
            status="running",
            started_at__isnull=False,
            started_at__lt=cutoff,
        ).select_related("verification")
    )

    for run in stuck_runs:
        verification = run.verification
        summary = (
            "Re-verification worker did not complete within the allowed "
            "time window."
        )
        verification.status = "failed"
        verification.summary = summary
        verification.save(update_fields=["status", "summary"])
        DeliveryDecision.objects.filter(
            verification=verification,
            is_current=True,
        ).exclude(status="stale").update(
            status="stale",
            invalidated_at=now,
        )
        run.status = "failed"
        run.completed_at = now
        run.save(update_fields=["status", "completed_at"])

    return stuck_runs


@transaction.atomic
def complete_reverification_run(
    *,
    run_id,
    status,
    summary="",
    confidence=None,
    evidence=None,
):
    """Persist a re-verification conclusion and complete its run.

    The caller supplies fresh evidence selected by a rule-based or AI
    verification engine. This lifecycle function owns the durable state
    transition; it deliberately does not decide whether code satisfies a
    requirement.
    """

    if status not in FINAL_VERIFICATION_STATUSES:
        raise ValueError(f"Invalid final verification status: {status}")

    if confidence is not None and not 0 <= confidence <= 1:
        raise ValueError("Confidence must be between 0 and 1.")

    run = VerificationRun.objects.select_for_update().select_related(
        "verification",
    ).get(pk=run_id)

    if run.status != "running":
        raise ValueError("Only a running re-verification can be completed.")

    verification = run.verification
    evidence = list(evidence or [])
    invalid_evidence = [
        item
        for item in evidence
        if item.requirement_id != verification.requirement_id
    ]
    if invalid_evidence:
        raise ValueError(
            "Re-verification evidence must belong to the same requirement."
        )
    if confidence is not None:
        validate_evaluator_conclusion(
            requirement=verification.requirement,
            evidence=evidence,
            conclusion={
                "status": status,
                "summary": summary,
                "confidence": confidence,
                "evidence": evidence,
            },
        )

    for evidence_item in evidence:
        VerificationEvidence.objects.get_or_create(
            verification=verification,
            evidence=evidence_item,
        )

    verification.status = status
    verification.summary = summary
    verification.confidence = confidence
    if status in {"verified", "partial"}:
        verification.verified_at = timezone.now()
        verification.invalidated_at = None
    verification.save(
        update_fields=[
            "status",
            "summary",
            "confidence",
            "verified_at",
            "invalidated_at",
        ],
    )

    run.status = "failed" if status == "failed" else "completed"
    run.completed_at = timezone.now()
    run.save(update_fields=["status", "completed_at"])
    return verification


def process_next_reverification_run(
    *,
    evaluator=None,
    test_runner=None,
    source_evidence_collector=None,
):
    """Process the oldest queued run.

    Collects evidence, runs criteria evaluation, and produces a more
    detailed top-level summary that includes both evidence details and
    criterion results.
    """

    queued_run = VerificationRun.objects.filter(
        status="queued",
    ).order_by("requested_at").first()
    if queued_run is None:
        return None

    run = claim_reverification_run(run_id=queued_run.id)
    if run is None:
        return None

    verification = run.verification
    pull_request = run.triggering_changed_file.commit.pull_request
    if pull_request is None:
        return complete_reverification_run(
            run_id=run.id,
            status="unverified",
            summary=(
                "Re-verification could not collect code evidence because "
                "the triggering change is not associated with a pull request."
            ),
        )

    ingest_changed_file_evidence(
        requirement=verification.requirement,
        pull_request=pull_request,
    )
    if source_evidence_collector is not None:
        try:
            source_evidence_collector(
                requirement=verification.requirement,
                pull_request=pull_request,
            )
        except GitHubAPIError as error:
            logger.exception(
                "GitHub source collection failed for verification run %s.",
                run.id,
            )
            complete_reverification_run(
                run_id=run.id,
                status="failed",
                summary="GitHub source retrieval failed. See backend logs.",
                confidence=0.0,
            )
            raise VerificationProcessingError(
                run_id=run.id,
                stage="GitHub source retrieval",
            ) from error
    if test_runner is not None:
        execute_test_run(
            verification_run=run,
            runner=test_runner,
        )
    current_evidence = Evidence.objects.filter(
        requirement=verification.requirement,
        pull_request=pull_request,
        status__in=["valid", "invalid"],
    ).order_by("id")

    try:
        if evaluator is None:
            conclusion = evaluate(
                verification.requirement,
                current_evidence,
            )
        else:
            conclusion = evaluator.evaluate(
                verification.requirement,
                current_evidence,
            )
            validate_evaluator_conclusion(
                requirement=verification.requirement,
                evidence=current_evidence,
                conclusion=conclusion,
            )
    except LLMProviderError as error:
        logger.exception(
            "LLM evaluation failed for verification run %s.",
            run.id,
        )
        complete_reverification_run(
            run_id=run.id,
            status="failed",
            summary="LLM evaluation failed. See backend logs.",
            confidence=0.0,
        )
        raise VerificationProcessingError(
            run_id=run.id,
            stage="LLM evaluation",
            reason=str(error),
        ) from error

    try:
        execute_criteria(
            verification=verification,
            evidence=current_evidence,
            evaluator=evaluator,
        )
    except LLMProviderError as error:
        logger.exception(
            "LLM criterion evaluation failed for verification run %s.",
            run.id,
        )
        complete_reverification_run(
            run_id=run.id,
            status="failed",
            summary="LLM criterion evaluation failed. See backend logs.",
            confidence=0.0,
        )
        raise VerificationProcessingError(
            run_id=run.id,
            stage="LLM criterion evaluation",
            reason=str(error),
        ) from error

    criteria_conclusion = _criteria_outcome_for_verification(verification)
    if criteria_conclusion is not None:
        conclusion = {
            **conclusion,
            "status": criteria_conclusion["status"],
            "summary": criteria_conclusion["summary"],
            "confidence": criteria_conclusion["confidence"],
            "evidence": list(current_evidence),
        }

    # Enhance the top-level summary with criterion results for more detail
    base_summary = conclusion.get("summary", "")
    criteria_part = _build_criteria_summary(verification)
    if criteria_part:
        enhanced_summary = (base_summary + criteria_part).strip()
        conclusion = {**conclusion, "summary": enhanced_summary}

    verification = complete_reverification_run(
        run_id=run.id,
        **conclusion,
    )
    create_delivery_decision(verification=verification)
    return verification
