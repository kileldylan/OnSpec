import pytest

from Requora_backend.RequoraApp.models import (
    ChangedFile,
    Commit,
    Evidence,
    PullRequest,
    Repository,
    Requirement,
    RequirementCriterion,
    TestExecution,
    Verification,
    VerificationRun,
)
from Requora_backend.integrations.verification.execution import (
    TestExecutionResult,
)
from Requora_backend.integrations.verification.service import (
    process_next_reverification_run,
)


class FakeRunner:
    command = ["pytest", "-q"]

    def __init__(self, result):
        self.result = result

    def run(self):
        return self.result


@pytest.fixture
def queued_verification():
    repository = Repository.objects.create(
        github_id=99200,
        owner="Requora",
        name="execution",
        full_name="Requora/execution",
    )
    requirement = Requirement.objects.create(
        repository=repository,
        external_id="Requora-EXEC",
        source="manual",
        title="Authentication tests pass",
    )
    criterion = RequirementCriterion.objects.create(
        requirement=requirement,
        text="Authentication has automated tests.",
        category="test",
    )
    pull_request = PullRequest.objects.create(
        repository=repository,
        github_id=99201,
        number=10,
        title="Add authentication tests",
        author="Requora",
        source_branch="feature/auth-tests",
        target_branch="main",
        base_sha="b" * 40,
        head_sha="a" * 40,
        created_at="2026-08-20T07:00:00Z",
        updated_at="2026-08-20T07:00:00Z",
    )
    commit = Commit.objects.create(
        repository=repository,
        pull_request=pull_request,
        sha="a" * 40,
        message="Add authentication tests",
        author="Requora",
        committed_at="2026-08-20T07:00:00Z",
    )
    changed_file = ChangedFile.objects.create(
        commit=commit,
        filename="auth/tests.py",
        status="modified",
    )
    verification = Verification.objects.create(
        requirement=requirement,
        pull_request=pull_request,
        status="stale",
    )
    run = VerificationRun.objects.create(
        verification=verification,
        triggering_changed_file=changed_file,
        reason="Authentication code changed.",
    )
    return verification, run, criterion


@pytest.mark.django_db
def test_reverification_persists_passing_test_evidence(queued_verification):
    verification, run, criterion = queued_verification
    runner = FakeRunner(TestExecutionResult(
        status="passed",
        exit_code=0,
        stdout="4 passed",
        duration_ms=120,
    ))

    result = process_next_reverification_run(test_runner=runner)

    assert result == verification
    execution = TestExecution.objects.get(verification_run=run)
    assert execution.status == "passed"
    assert execution.exit_code == 0
    assert execution.stdout == "4 passed"

    evidence = Evidence.objects.get(
        requirement=verification.requirement,
        pull_request=verification.pull_request,
        evidence_type="test",
    )
    assert evidence.status == "valid"
    assert evidence.metadata["execution_id"] == execution.id
    assert verification.criterion_results.get(criterion=criterion).status == (
        "satisfied"
    )
    assert verification.decisions.get(is_current=True).status == "partial"


@pytest.mark.django_db
def test_reverification_persists_failed_test_evidence(queued_verification):
    verification, run, criterion = queued_verification
    runner = FakeRunner(TestExecutionResult(
        status="failed",
        exit_code=1,
        stdout="1 failed",
        stderr="AssertionError",
        duration_ms=90,
    ))

    process_next_reverification_run(test_runner=runner)

    execution = TestExecution.objects.get(verification_run=run)
    assert execution.status == "failed"
    evidence = Evidence.objects.get(
        requirement=verification.requirement,
        pull_request=verification.pull_request,
        evidence_type="test",
    )
    assert evidence.status == "invalid"
    assert verification.criterion_results.get(criterion=criterion).status == (
        "failed"
    )
    assert verification.decisions.get(is_current=True).status == "unverified"
