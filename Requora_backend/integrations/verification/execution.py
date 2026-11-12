"""Test execution adapters and conversion of results into evidence."""

from dataclasses import dataclass
import subprocess
import sys
import time
from pathlib import Path

from django.db import transaction
from django.utils import timezone

from Requora_backend.RequoraApp.models import Commit, Evidence, TestExecution


TEST_EXECUTION_STATUSES = {
    "passed",
    "failed",
    "timed_out",
    "error",
}


@dataclass(frozen=True)
class TestExecutionResult:
    status: str
    exit_code: int | None = None
    stdout: str = ""
    stderr: str = ""
    duration_ms: int | None = None
    metadata: dict | None = None


class PytestRunner:
    """Run an explicit pytest command in a supplied checkout directory."""

    def __init__(self, *, workspace, command=None, timeout=300):
        self.workspace = Path(workspace)
        self.command = list(command or [sys.executable, "-m", "pytest", "-q"])
        self.timeout = timeout

    def run(self):
        return _run_command(
            command=self.command,
            workspace=self.workspace,
            timeout=self.timeout,
        )


class DockerPytestRunner:
    """Run pytest in a constrained, network-isolated Docker container."""

    def __init__(self, *, workspace, image, timeout=300):
        self.workspace = Path(workspace).resolve()
        self.timeout = timeout
        self.command = [
            "docker",
            "run",
            "--rm",
            "--network=none",
            "--read-only",
            "--cap-drop=ALL",
            "--security-opt=no-new-privileges",
            "--pids-limit=256",
            "--memory=1g",
            "--cpus=2",
            "--tmpfs",
            "/tmp:rw,noexec,nosuid,size=512m",
            "--volume",
            f"{self.workspace}:/workspace:ro",
            "--workdir",
            "/workspace",
            image,
            "pytest",
            "-q",
        ]

    def run(self):
        return _run_command(
            command=self.command,
            workspace=self.workspace,
            timeout=self.timeout,
        )


def _run_command(*, command, workspace, timeout):
    started = time.monotonic()
    try:
        completed = subprocess.run(
            command,
            cwd=workspace,
            capture_output=True,
            text=True,
            timeout=timeout,
            check=False,
        )
    except subprocess.TimeoutExpired as error:
        return TestExecutionResult(
            status="timed_out",
            stdout=_decode_output(error.stdout),
            stderr=_decode_output(error.stderr),
            duration_ms=_duration_ms(started),
            metadata={"timeout_seconds": timeout},
        )
    except OSError as error:
        return TestExecutionResult(
            status="error",
            stderr=str(error),
            duration_ms=_duration_ms(started),
        )

    return TestExecutionResult(
        status="passed" if completed.returncode == 0 else "failed",
        exit_code=completed.returncode,
        stdout=completed.stdout,
        stderr=completed.stderr,
        duration_ms=_duration_ms(started),
    )


def _decode_output(output):
    if output is None:
        return ""
    if isinstance(output, bytes):
        return output.decode(errors="replace")
    return output


def _duration_ms(started):
    return int((time.monotonic() - started) * 1000)


@transaction.atomic
def execute_test_run(*, verification_run, runner):
    """Run a test adapter and persist its result as test evidence."""

    verification_run = verification_run.__class__.objects.select_related(
        "verification__requirement",
        "verification__pull_request",
    ).get(pk=verification_run.pk)
    verification = verification_run.verification
    pull_request = verification.pull_request
    commit = None
    if pull_request is not None:
        commit = Commit.objects.filter(
            pull_request=pull_request,
            sha=pull_request.head_sha,
        ).first()

    execution = TestExecution.objects.create(
        verification_run=verification_run,
        commit=commit,
        command=list(getattr(runner, "command", [])),
        status="running",
        started_at=timezone.now(),
    )

    try:
        result = runner.run()
        if result.status not in TEST_EXECUTION_STATUSES:
            raise ValueError(f"Invalid test execution status: {result.status}")
    except Exception as error:
        result = TestExecutionResult(
            status="error",
            stderr=str(error),
        )

    completed_at = timezone.now()
    execution.status = result.status
    execution.exit_code = result.exit_code
    execution.stdout = result.stdout
    execution.stderr = result.stderr
    execution.duration_ms = result.duration_ms
    execution.metadata = result.metadata or {}
    execution.completed_at = completed_at
    execution.save(update_fields=[
        "status",
        "exit_code",
        "stdout",
        "stderr",
        "duration_ms",
        "metadata",
        "completed_at",
    ])

    head_sha = pull_request.head_sha if pull_request is not None else None
    evidence_key = f"test-execution:{execution.pk}"
    evidence_status = "valid" if result.status == "passed" else "invalid"
    evidence, _ = Evidence.objects.update_or_create(
        requirement=verification.requirement,
        pull_request=pull_request,
        commit=commit,
        evidence_type="test",
        metadata__execution_key=evidence_key,
        defaults={
            "status": evidence_status,
            "description": (
                f"Automated pytest execution {result.status}."
            ),
            "metadata": {
                "source": "requora",
                "execution_key": evidence_key,
                "execution_id": execution.id,
                "head_sha": head_sha,
                "command": execution.command,
                "exit_code": result.exit_code,
                "duration_ms": result.duration_ms,
            },
        },
    )
    return execution, evidence
