import pytest

from ACI_backend.ACIApp.models import (
    ChangedFile,
    Commit,
    Evidence,
    PullRequest,
    Repository,
    Requirement,
    Verification,
)
from ACI_backend.integrations.verification.criteria import (
    create_criterion,
    deactivate_criterion,
    generate_initial_criteria,
    list_active_criteria,
    record_criterion_verification,
    execute_criteria,
    update_criterion,
)


@pytest.fixture
def requirement():
    repository = Repository.objects.create(
        github_id=99001,
        owner="aci",
        name="criteria",
        full_name="aci/criteria",
    )
    return Requirement.objects.create(
        repository=repository,
        external_id="ACI-1",
        source="manual",
        title="Reset passwords",
    )


@pytest.mark.django_db
def test_criteria_service_persists_structured_expectations(requirement):
    criteria = generate_initial_criteria(requirement=requirement, criteria=[
        {"text": "A reset flow exists.", "category": "behavior"},
        {
            "text": "A reset email is sent.",
            "category": "integration",
            "expectations": {"path_patterns": ["**/email*.py"]},
        },
    ])

    assert [criterion.order for criterion in criteria] == [0, 1]
    assert criteria[1].expectations["path_patterns"] == ["**/email*.py"]
    assert list(list_active_criteria(requirement=requirement)) == criteria

    update_criterion(criterion=criteria[0], priority=10)
    deactivate_criterion(criterion=criteria[1])
    assert criteria[0].priority == 10
    assert list(list_active_criteria(requirement=requirement)) == [criteria[0]]


@pytest.mark.django_db
def test_criterion_results_retain_evidence_traceability(requirement):
    criterion = create_criterion(requirement=requirement, text="Reset view exists.")
    pull_request = PullRequest.objects.create(
        repository=requirement.repository,
        github_id=99002,
        number=1,
        title="Reset passwords",
        author="aci",
        source_branch="feature/reset",
        target_branch="main",
        base_sha="b" * 40,
        head_sha="a" * 40,
        created_at="2026-08-19T07:00:00Z",
        updated_at="2026-08-19T07:00:00Z",
    )
    verification = Verification.objects.create(
        requirement=requirement,
        pull_request=pull_request,
        status="partial",
    )
    evidence = Evidence.objects.create(
        requirement=requirement,
        pull_request=pull_request,
        evidence_type="code",
    )
    result = record_criterion_verification(
        verification=verification,
        criterion=criterion,
        status="satisfied",
        evidence=[evidence],
    )

    assert result in verification.criterion_results.all()
    assert result.evidence_links.get().evidence == evidence
    assert evidence.criterion_verification_links.get().criterion_verification == result
    assert verification.evidence_links.get().evidence == evidence


@pytest.mark.django_db
def test_execute_criteria_matches_current_evidence_to_expectations(requirement):
    criterion = create_criterion(
        requirement=requirement,
        text="The reset endpoint is implemented.",
        expectations={
            "evidence_types": "code",
            "path_patterns": ["accounts/*.py"],
        },
    )
    pull_request = PullRequest.objects.create(
        repository=requirement.repository,
        github_id=99003,
        number=2,
        title="Implement reset endpoint",
        author="aci",
        source_branch="feature/reset-endpoint",
        target_branch="main",
        base_sha="b" * 40,
        head_sha="a" * 40,
        created_at="2026-08-19T07:00:00Z",
        updated_at="2026-08-19T07:00:00Z",
    )
    verification = Verification.objects.create(
        requirement=requirement,
        pull_request=pull_request,
    )
    commit = Commit.objects.create(
        repository=requirement.repository,
        pull_request=pull_request,
        sha="c" * 40,
        message="Implement reset endpoint",
        author="aci",
        committed_at="2026-08-19T07:00:00Z",
    )
    changed_file = ChangedFile.objects.create(
        commit=commit,
        filename="accounts/reset.py",
        additions=2,
        changes=2,
        patch=(
            "@@ -1,0 +1,2 @@\n"
            "+def reset_password(user):\n"
            "+    return create_reset_token(user)"
        ),
    )
    evidence = Evidence.objects.create(
        requirement=requirement,
        pull_request=pull_request,
        commit=commit,
        changed_file=changed_file,
        evidence_type="code",
        status="valid",
        metadata={
            "filename": "accounts/reset.py",
            "evidence_role": "implementation",
            "snippet": (
                "def reset_password(user):\n"
                "    return create_reset_token(user)"
            ),
            "line_start": 1,
            "line_end": 2,
        },
    )

    results = execute_criteria(
        verification=verification,
        evidence=[evidence],
    )

    assert len(results) == 1
    assert results[0].criterion == criterion
    assert results[0].status == "satisfied"
    assert results[0].summary == (
        "Relevant implementation changes in accounts/reset.py:1-2."
    )
    assert results[0].evidence_links.get().evidence == evidence


@pytest.mark.django_db
def test_documentation_change_does_not_satisfy_implementation_criterion(requirement):
    create_criterion(
        requirement=requirement,
        text="The reset endpoint is implemented.",
    )
    pull_request = PullRequest.objects.create(
        repository=requirement.repository,
        github_id=99005,
        number=4,
        title="Document reset endpoint",
        author="aci",
        source_branch="docs/reset",
        target_branch="main",
        base_sha="b" * 40,
        head_sha="a" * 40,
        created_at="2026-08-19T07:00:00Z",
        updated_at="2026-08-19T07:00:00Z",
    )
    verification = Verification.objects.create(
        requirement=requirement,
        pull_request=pull_request,
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

    results = execute_criteria(
        verification=verification,
        evidence=[documentation],
    )

    assert results[0].status == "missing"
    assert results[0].evidence_links.count() == 0


@pytest.mark.django_db
def test_execute_criteria_marks_unmatched_required_criterion_missing(requirement):
    create_criterion(
        requirement=requirement,
        text="The reset flow has automated tests.",
        category="test",
    )
    pull_request = PullRequest.objects.create(
        repository=requirement.repository,
        github_id=99004,
        number=3,
        title="Implement reset flow",
        author="aci",
        source_branch="feature/reset-flow",
        target_branch="main",
        base_sha="b" * 40,
        head_sha="a" * 40,
        created_at="2026-08-19T07:00:00Z",
        updated_at="2026-08-19T07:00:00Z",
    )
    verification = Verification.objects.create(
        requirement=requirement,
        pull_request=pull_request,
    )
    code_evidence = Evidence.objects.create(
        requirement=requirement,
        pull_request=pull_request,
        evidence_type="code",
        status="valid",
    )

    results = execute_criteria(
        verification=verification,
        evidence=[code_evidence],
    )

    assert results[0].status == "missing"
