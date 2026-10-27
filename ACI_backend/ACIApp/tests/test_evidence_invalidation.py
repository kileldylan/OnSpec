import pytest
from datetime import timedelta
from django.utils import timezone

from ACI_backend.ACIApp.models import (
    ChangedFile,
    Commit,
    Evidence,
    EvidenceInvalidation,
    PullRequest,
    Repository,
    Requirement,
    Verification,
    VerificationEvidence,
    VerificationRun,
)
from ACI_backend.integrations.github.service import process_github_evidence_event
from ACI_backend.integrations.github.client import GitHubAPIError
from ACI_backend.integrations.verification.errors import (
    LLMProviderError,
    VerificationProcessingError,
)
from ACI_backend.integrations.verification.service import (
    claim_reverification_run,
    complete_reverification_run,
    evaluate,
    evaluate_reverification_evidence,
    invalidate_evidence_for_changed_file,
    process_next_reverification_run,
    recover_stuck_reverification_runs,
)


def create_pull_request(repository, *, number, sha):
    return PullRequest.objects.create(
        repository=repository,
        github_id=100000 + number,
        number=number,
        title="Update authentication",
        author="kilel",
        source_branch=f"feature/auth-{number}",
        target_branch="main",
        base_sha="b" * 40,
        head_sha=sha,
        state="open",
        is_merged=False,
        created_at="2026-08-17T10:00:00Z",
        updated_at="2026-08-17T10:00:00Z",
    )


@pytest.mark.django_db
def test_changed_file_invalidates_prior_evidence_and_verification():
    repository = Repository.objects.create(
        github_id=123456,
        owner="kilel",
        name="aci-demo",
        full_name="kilel/aci-demo",
    )
    requirement = Requirement.objects.create(
        repository=repository,
        external_id="AUTH-3",
        source="jira",
        title="Users can authenticate",
    )

    original_pr = create_pull_request(
        repository,
        number=3,
        sha="a" * 40,
    )
    original_commit = Commit.objects.create(
        repository=repository,
        pull_request=original_pr,
        sha="c" * 40,
        message="Implement authentication",
        author="kilel",
        committed_at="2026-08-17T10:00:00Z",
    )
    original_file = ChangedFile.objects.create(
        commit=original_commit,
        filename="auth/service.py",
        status="added",
        additions=30,
        changes=30,
    )
    evidence = Evidence.objects.create(
        requirement=requirement,
        pull_request=original_pr,
        commit=original_commit,
        changed_file=original_file,
        evidence_type="code",
        status="valid",
        description="Authentication service implements the requirement.",
    )
    verification = Verification.objects.create(
        requirement=requirement,
        pull_request=original_pr,
        status="verified",
        summary="Authentication is verified.",
        confidence=0.95,
    )
    VerificationEvidence.objects.create(
        verification=verification,
        evidence=evidence,
    )

    later_pr = create_pull_request(
        repository,
        number=517,
        sha="d" * 40,
    )
    later_commit = Commit.objects.create(
        repository=repository,
        pull_request=later_pr,
        sha="e" * 40,
        message="Refactor authentication service",
        author="kilel",
        committed_at="2026-08-18T10:00:00Z",
    )
    changed_file = ChangedFile.objects.create(
        commit=later_commit,
        filename="auth/service.py",
        status="modified",
        additions=10,
        deletions=8,
        changes=18,
    )

    invalidations = invalidate_evidence_for_changed_file(changed_file)

    assert invalidations.count() == 1
    invalidation = invalidations.get()
    assert invalidation.evidence == evidence
    assert invalidation.triggering_changed_file == changed_file
    assert invalidation.reason == (
        "PR #517 changed auth/service.py."
    )

    evidence.refresh_from_db()
    verification.refresh_from_db()
    assert evidence.status == "stale"
    assert verification.status == "stale"
    assert verification.invalidated_at is not None

    run = VerificationRun.objects.get(verification=verification)
    assert run.status == "queued"
    assert run.triggering_changed_file == changed_file
    assert run.reason == "PR #517 changed auth/service.py."

    claimed_run = claim_reverification_run(run_id=run.id)
    assert claimed_run.status == "running"
    assert claimed_run.started_at is not None

    fresh_evidence = Evidence.objects.create(
        requirement=requirement,
        pull_request=later_pr,
        commit=later_commit,
        changed_file=changed_file,
        evidence_type="code",
        status="valid",
        description="Authentication service was re-verified.",
    )
    completed_verification = complete_reverification_run(
        run_id=run.id,
        status="verified",
        summary="Authentication is verified against the latest change.",
        confidence=0.96,
        evidence=[fresh_evidence],
    )

    completed_verification.refresh_from_db()
    run.refresh_from_db()
    assert completed_verification.status == "verified"
    assert completed_verification.invalidated_at is None
    assert completed_verification.evidence_links.filter(
        evidence=fresh_evidence,
    ).exists()
    assert run.status == "completed"
    assert run.completed_at is not None

    invalidate_evidence_for_changed_file(changed_file)
    assert EvidenceInvalidation.objects.count() == 1
    assert VerificationRun.objects.count() == 1


@pytest.mark.django_db
def test_process_next_reverification_run_collects_fresh_code_evidence():
    repository = Repository.objects.create(
        github_id=789012,
        owner="kilel",
        name="aci-demo-two",
        full_name="kilel/aci-demo-two",
    )
    requirement = Requirement.objects.create(
        repository=repository,
        external_id="AUTH-4",
        source="jira",
        title="Users can authenticate",
    )
    pull_request = create_pull_request(
        repository,
        number=517,
        sha="f" * 40,
    )
    commit = Commit.objects.create(
        repository=repository,
        pull_request=pull_request,
        sha="g" * 40,
        message="Refactor authentication service",
        author="kilel",
        committed_at="2026-08-18T10:00:00Z",
    )
    changed_file = ChangedFile.objects.create(
        commit=commit,
        filename="auth/service.py",
        status="modified",
        additions=10,
        deletions=8,
        changes=18,
        patch=(
            "@@ -1,3 +1,5 @@\n"
            "+def authenticate_user(credentials):\n"
            "+    return authentication_service.authenticate(credentials)"
        ),
    )
    verification = Verification.objects.create(
        requirement=requirement,
        pull_request=pull_request,
        status="stale",
    )
    run = VerificationRun.objects.create(
        verification=verification,
        triggering_changed_file=changed_file,
        reason="PR #517 changed auth/service.py.",
    )

    result = process_next_reverification_run()

    assert result == verification
    verification.refresh_from_db()
    run.refresh_from_db()
    assert verification.status == "partial"
    assert verification.summary == (
        "Code evidence collected for PR #517. "
        "Changes in 1 files: auth/service.py. "
        "Missing valid CI and test evidence."
    )
    assert run.status == "completed"
    assert verification.evidence_links.filter(
        evidence__changed_file=changed_file,
        evidence__status="valid",
    ).exists()
    assert process_next_reverification_run() is None


@pytest.mark.django_db
def test_github_source_failure_marks_run_failed_and_reports_stage():
    repository = Repository.objects.create(
        github_id=789013,
        owner="kilel",
        name="aci-demo-source-error",
        full_name="kilel/aci-demo-source-error",
    )
    requirement = Requirement.objects.create(
        repository=repository,
        external_id="AUTH-8",
        source="jira",
        title="Users can authenticate",
    )
    pull_request = create_pull_request(
        repository,
        number=518,
        sha="l" * 40,
    )
    commit = Commit.objects.create(
        repository=repository,
        pull_request=pull_request,
        sha="m" * 40,
        message="Update authentication",
        author="kilel",
        committed_at="2026-08-18T10:00:00Z",
    )
    changed_file = ChangedFile.objects.create(
        commit=commit,
        filename="README.md",
        status="modified",
    )
    verification = Verification.objects.create(
        requirement=requirement,
        pull_request=pull_request,
        status="pending",
    )
    run = VerificationRun.objects.create(
        verification=verification,
        triggering_changed_file=changed_file,
        reason="Initial verification.",
    )

    def failed_source_collection(**kwargs):
        raise GitHubAPIError("GitHub API request failed.")

    with pytest.raises(VerificationProcessingError) as error:
        process_next_reverification_run(
            source_evidence_collector=failed_source_collection,
        )

    assert error.value.run_id == run.id
    assert error.value.stage == "GitHub source retrieval"
    run.refresh_from_db()
    verification.refresh_from_db()
    assert run.status == "failed"
    assert verification.status == "failed"
    assert "See backend logs" in verification.summary


@pytest.mark.django_db
def test_llm_failure_marks_run_failed_and_reports_stage():
    repository = Repository.objects.create(
        github_id=789014,
        owner="kilel",
        name="aci-demo-llm-error",
        full_name="kilel/aci-demo-llm-error",
    )
    requirement = Requirement.objects.create(
        repository=repository,
        external_id="AUTH-9",
        source="jira",
        title="Users can authenticate",
    )
    pull_request = create_pull_request(
        repository,
        number=519,
        sha="n" * 40,
    )
    commit = Commit.objects.create(
        repository=repository,
        pull_request=pull_request,
        sha="o" * 40,
        message="Update authentication",
        author="kilel",
        committed_at="2026-08-18T10:00:00Z",
    )
    changed_file = ChangedFile.objects.create(
        commit=commit,
        filename="README.md",
        status="modified",
    )
    verification = Verification.objects.create(
        requirement=requirement,
        pull_request=pull_request,
        status="pending",
    )
    run = VerificationRun.objects.create(
        verification=verification,
        triggering_changed_file=changed_file,
        reason="Initial verification.",
    )

    class FailedEvaluator:
        def evaluate(self, requirement, evidence):
            raise LLMProviderError("Provider unavailable.")

    with pytest.raises(VerificationProcessingError) as error:
        process_next_reverification_run(evaluator=FailedEvaluator())

    assert error.value.run_id == run.id
    assert error.value.stage == "LLM evaluation"
    assert error.value.reason == "Provider unavailable."
    run.refresh_from_db()
    verification.refresh_from_db()
    assert run.status == "failed"
    assert verification.status == "failed"
    assert "See backend logs" in verification.summary


@pytest.mark.django_db
def test_evidence_policy_verifies_when_code_test_and_ci_are_valid():
    repository = Repository.objects.create(
        github_id=345678,
        owner="kilel",
        name="aci-demo-three",
        full_name="kilel/aci-demo-three",
    )
    requirement = Requirement.objects.create(
        repository=repository,
        external_id="AUTH-5",
        source="jira",
        title="Users can authenticate",
    )
    pull_request = create_pull_request(
        repository,
        number=18,
        sha="h" * 40,
    )
    for evidence_type in ["code", "test", "ci"]:
        Evidence.objects.create(
            requirement=requirement,
            pull_request=pull_request,
            evidence_type=evidence_type,
            status="valid",
            description=f"Valid {evidence_type} evidence.",
            metadata=(
                {
                    "filename": "src/auth.py",
                    "evidence_role": "implementation",
                    "snippet": "def authenticate_user(credentials):",
                    "line_start": 12,
                    "line_end": 12,
                }
                if evidence_type == "code"
                else {}
            ),
        )

    conclusion = evaluate_reverification_evidence(
        requirement=requirement,
        pull_request=pull_request,
    )

    assert conclusion["status"] == "verified"
    assert conclusion["confidence"] == 0.9
    assert conclusion["summary"] == (
        "PR #18 has valid code, test, and CI evidence. "
        "Changes in 1 files: src/auth.py. "
        "(tests: Valid test evidence.; CI: Valid ci evidence.)"
    )
    assert len(conclusion["evidence"]) == 3

    stable_conclusion = evaluate(
        requirement,
        Evidence.objects.filter(
            requirement=requirement,
            pull_request=pull_request,
            status="valid",
        ),
    )
    assert stable_conclusion["status"] == "verified"
    assert stable_conclusion["evidence"]


@pytest.mark.django_db
def test_evidence_policy_does_not_count_documentation_as_code():
    repository = Repository.objects.create(
        github_id=345679,
        owner="kilel",
        name="aci-demo-docs",
        full_name="kilel/aci-demo-docs",
    )
    requirement = Requirement.objects.create(
        repository=repository,
        external_id="AUTH-6",
        source="jira",
        title="Users can reset passwords",
    )
    pull_request = create_pull_request(
        repository,
        number=19,
        sha="i" * 40,
    )
    documentation = Evidence.objects.create(
        requirement=requirement,
        pull_request=pull_request,
        evidence_type="code",
        status="valid",
        metadata={
            "filename": "README.md",
            "evidence_role": "documentation",
            "snippet": "",
        },
    )

    conclusion = evaluate_reverification_evidence(
        requirement=requirement,
        pull_request=pull_request,
    )

    assert conclusion["status"] == "unverified"
    assert conclusion["confidence"] == 0.0
    assert documentation in conclusion["evidence"]


@pytest.mark.django_db
def test_evidence_policy_fails_when_current_github_check_is_invalid():
    repository = Repository.objects.create(
        github_id=567890,
        owner="kilel",
        name="aci-demo-five",
        full_name="kilel/aci-demo-five",
    )
    requirement = Requirement.objects.create(
        repository=repository,
        external_id="AUTH-7",
        source="jira",
        title="Users can authenticate",
    )
    pull_request = create_pull_request(
        repository,
        number=23,
        sha="k" * 40,
    )
    for evidence_type in ["code", "test", "ci"]:
        Evidence.objects.create(
            requirement=requirement,
            pull_request=pull_request,
            evidence_type=evidence_type,
            status="valid",
            description=f"Valid {evidence_type} evidence.",
        )
    Evidence.objects.create(
        requirement=requirement,
        pull_request=pull_request,
        evidence_type="ci",
        status="invalid",
        metadata={
            "source": "github",
            "head_sha": pull_request.head_sha,
            "context": "build",
            "state": "failure",
        },
    )

    conclusion = evaluate_reverification_evidence(
        requirement=requirement,
        pull_request=pull_request,
    )

    assert conclusion["status"] == "failed"
    assert conclusion["confidence"] == 0.0
    assert conclusion["summary"] == (
        "A test or CI check failed for the current head of PR #23."
    )


@pytest.mark.django_db
def test_github_check_run_evidence_is_idempotent_and_stale_aware():
    repository = Repository.objects.create(
        github_id=456789,
        owner="kilel",
        name="aci-demo-four",
        full_name="kilel/aci-demo-four",
    )
    requirement = Requirement.objects.create(
        repository=repository,
        external_id="AUTH-6",
        source="jira",
        title="Users can authenticate",
    )
    pull_request = create_pull_request(
        repository,
        number=22,
        sha="i" * 40,
    )
    requirement.pull_request_links.create(pull_request=pull_request)

    first_payload = {
        "repository": {"id": repository.github_id},
        "check_run": {
            "id": 1,
            "name": "pytest",
            "status": "completed",
            "conclusion": "success",
            "head_sha": pull_request.head_sha,
            "pull_requests": [{"number": pull_request.number}],
        },
    }

    first = process_github_evidence_event("check_run", first_payload)
    repeated = process_github_evidence_event("check_run", first_payload)

    assert len(first) == 1
    assert repeated[0].id == first[0].id
    assert Evidence.objects.count() == 1
    assert first[0].evidence_type == "test"
    assert first[0].metadata["head_sha"] == pull_request.head_sha

    second_commit = Commit.objects.create(
        repository=repository,
        pull_request=pull_request,
        sha="j" * 40,
        message="Update authentication",
        author="kilel",
        committed_at="2026-08-19T10:00:00Z",
    )
    second_payload = {
        **first_payload,
        "check_run": {
            **first_payload["check_run"],
            "id": 2,
            "head_sha": second_commit.sha,
        },
    }

    second = process_github_evidence_event("check_run", second_payload)

    first[0].refresh_from_db()
    assert first[0].status == "stale"
    assert second[0].status == "valid"
    assert Evidence.objects.count() == 2


@pytest.mark.django_db
def test_new_github_test_and_ci_results_stale_old_evidence_once():
    repository = Repository.objects.create(
        github_id=678901,
        owner="kilel",
        name="aci-demo-six",
        full_name="kilel/aci-demo-six",
    )
    requirement = Requirement.objects.create(
        repository=repository,
        external_id="AUTH-8",
        source="jira",
        title="Users can authenticate",
    )
    pull_request = create_pull_request(
        repository,
        number=24,
        sha="m" * 40,
    )
    requirement.pull_request_links.create(pull_request=pull_request)
    old_commit = Commit.objects.create(
        repository=repository,
        pull_request=pull_request,
        sha=pull_request.head_sha,
        message="Implement authentication",
        author="kilel",
        committed_at="2026-08-19T10:00:00Z",
    )
    old_file = ChangedFile.objects.create(
        commit=old_commit,
        filename="auth/service.py",
        status="modified",
    )
    old_test = Evidence.objects.create(
        requirement=requirement,
        pull_request=pull_request,
        commit=old_commit,
        evidence_type="test",
        status="valid",
        metadata={
            "source": "github",
            "external_key": "check_run:pytest",
            "head_sha": old_commit.sha,
        },
    )
    old_ci = Evidence.objects.create(
        requirement=requirement,
        pull_request=pull_request,
        commit=old_commit,
        evidence_type="ci",
        status="valid",
        metadata={
            "source": "github",
            "external_key": "status:build",
            "head_sha": old_commit.sha,
        },
    )
    verification = Verification.objects.create(
        requirement=requirement,
        pull_request=pull_request,
        status="verified",
    )
    VerificationEvidence.objects.create(
        verification=verification,
        evidence=old_test,
    )
    VerificationEvidence.objects.create(
        verification=verification,
        evidence=old_ci,
    )
    new_commit = Commit.objects.create(
        repository=repository,
        pull_request=pull_request,
        sha="n" * 40,
        message="Update authentication",
        author="kilel",
        committed_at="2026-08-19T11:00:00Z",
    )
    ChangedFile.objects.create(
        commit=new_commit,
        filename=old_file.filename,
        status="modified",
    )

    process_github_evidence_event(
        "check_run",
        {
            "repository": {"id": repository.github_id},
            "check_run": {
                "id": 2,
                "name": "pytest",
                "status": "completed",
                "conclusion": "success",
                "head_sha": new_commit.sha,
                "pull_requests": [{"number": pull_request.number}],
            },
        },
    )
    process_github_evidence_event(
        "status",
        {
            "repository": {"id": repository.github_id},
            "sha": new_commit.sha,
            "context": "build",
            "state": "success",
        },
    )

    old_test.refresh_from_db()
    old_ci.refresh_from_db()
    verification.refresh_from_db()
    assert old_test.status == "stale"
    assert old_ci.status == "stale"
    assert verification.status == "stale"
    assert verification.runs.filter(status="queued").count() == 1


@pytest.mark.django_db
def test_stuck_reverification_run_is_failed_and_traceable():
    repository = Repository.objects.create(
        github_id=789123,
        owner="kilel",
        name="aci-demo-seven",
        full_name="kilel/aci-demo-seven",
    )
    requirement = Requirement.objects.create(
        repository=repository,
        external_id="AUTH-9",
        source="jira",
        title="Users can authenticate",
    )
    pull_request = create_pull_request(
        repository,
        number=25,
        sha="o" * 40,
    )
    commit = Commit.objects.create(
        repository=repository,
        pull_request=pull_request,
        sha="p" * 40,
        message="Implement authentication",
        author="kilel",
        committed_at="2026-08-19T10:00:00Z",
    )
    changed_file = ChangedFile.objects.create(
        commit=commit,
        filename="auth/service.py",
        status="modified",
    )
    verification = Verification.objects.create(
        requirement=requirement,
        pull_request=pull_request,
        status="stale",
    )
    started_at = timezone.now() - timedelta(hours=2)
    run = VerificationRun.objects.create(
        verification=verification,
        triggering_changed_file=changed_file,
        status="running",
        reason="Worker recovery test.",
        started_at=started_at,
    )

    recovered = recover_stuck_reverification_runs(
        timeout=timedelta(hours=1),
        now=timezone.now(),
    )

    assert [item.id for item in recovered] == [run.id]
    verification.refresh_from_db()
    run.refresh_from_db()
    assert verification.status == "failed"
    assert verification.summary == (
        "Re-verification worker did not complete within the allowed "
        "time window."
    )
    assert run.status == "failed"
    assert run.completed_at is not None
