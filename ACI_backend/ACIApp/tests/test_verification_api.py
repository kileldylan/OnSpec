import pytest
from django.contrib.auth import get_user_model
from django.urls import reverse
from rest_framework.test import APIClient

from ACI_backend.ACIApp.models import (
    ChangedFile,
    Commit,
    CriterionVerification,
    CriterionVerificationEvidence,
    DeliveryDecision,
    Evidence,
    EvidenceInvalidation,
    PullRequest,
    Repository,
    Requirement,
    RequirementCriterion,
    RequirementPullRequest,
    Verification,
    VerificationEvidence,
    VerificationRun,
)


def test_api_requires_authentication():
    response = APIClient().get(reverse("repository-list"))

    assert response.status_code in {401, 403}


@pytest.mark.django_db
def test_repository_creator_is_added_as_member():
    user = get_user_model().objects.create_user(
        username="repository-owner",
        password="test-password",
    )
    client = APIClient()
    client.force_authenticate(user=user)

    response = client.post(
        reverse("repository-list"),
        {
            "github_id": 987001,
            "owner": "aci",
            "name": "owned-repository",
            "full_name": "aci/owned-repository",
        },
        format="json",
    )

    assert response.status_code == 201
    repository = Repository.objects.get(full_name="aci/owned-repository")
    assert repository.members.filter(pk=user.pk).exists()


@pytest.mark.django_db
def test_repository_can_start_verification_for_selected_pr_and_requirement():
    user = get_user_model().objects.create_user(
        username="verification-starter",
        password="test-password",
    )
    repository = Repository.objects.create(
        github_id=987004,
        owner="aci",
        name="verification-target",
        full_name="aci/verification-target",
    )
    repository.members.add(user)
    pull_request = PullRequest.objects.create(
        repository=repository,
        github_id=987005,
        number=12,
        title="Implement authentication",
        author="kilel",
        source_branch="feature/auth",
        target_branch="main",
        base_sha="b" * 40,
        head_sha="a" * 40,
        state="open",
        is_merged=False,
        created_at="2026-08-18T10:00:00Z",
        updated_at="2026-08-18T10:00:00Z",
    )
    requirement = Requirement.objects.create(
        repository=repository,
        external_id="PROJ-123",
        source="jira",
        title="Users can authenticate",
    )
    commit = Commit.objects.create(
        repository=repository,
        pull_request=pull_request,
        sha="c" * 40,
        message="Implement authentication",
        author="kilel",
        committed_at="2026-08-18T10:30:00Z",
    )
    changed_file = ChangedFile.objects.create(
        commit=commit,
        filename="auth/service.py",
        status="modified",
    )

    client = APIClient()
    client.force_authenticate(user=user)
    response = client.post(
        reverse(
            "repository-start-verification",
            kwargs={"pk": repository.pk},
        ),
        {
            "pull_request_number": pull_request.number,
            "requirement_id": requirement.id,
        },
        format="json",
    )

    assert response.status_code == 201
    assert response.json()["verification"]["pull_request"]["id"] == pull_request.id
    assert response.json()["verification"]["requirement"]["id"] == requirement.id
    assert response.json()["run"]["status"] == "queued"
    assert response.json()["run"]["triggering_changed_file"] == changed_file.id
    assert RequirementPullRequest.objects.filter(
        requirement=requirement,
        pull_request=pull_request,
    ).exists()


@pytest.mark.django_db
def test_user_cannot_read_another_repository():
    user = get_user_model().objects.create_user(
        username="repository-reader",
        password="test-password",
    )
    visible = Repository.objects.create(
        github_id=987002,
        owner="aci",
        name="visible",
        full_name="aci/visible",
    )
    hidden = Repository.objects.create(
        github_id=987003,
        owner="aci",
        name="hidden",
        full_name="aci/hidden",
    )
    visible.members.add(user)
    client = APIClient()
    client.force_authenticate(user=user)

    list_response = client.get(reverse("repository-list"))
    hidden_response = client.get(
        reverse("repository-detail", kwargs={"pk": hidden.pk}),
    )

    assert [item["id"] for item in list_response.json()] == [visible.id]
    assert hidden_response.status_code == 404


@pytest.mark.django_db
def test_verification_api_exposes_stale_proof_and_queued_work():
    repository = Repository.objects.create(
        github_id=123456,
        owner="kilel",
        name="aci-demo",
        full_name="aci-demo",
    )
    user = get_user_model().objects.create_user(
        username="verification-reader",
        password="test-password",
    )
    repository.members.add(user)
    pull_request = PullRequest.objects.create(
        repository=repository,
        github_id=987654,
        number=517,
        title="Refactor authentication",
        author="kilel",
        source_branch="feature/auth-refactor",
        target_branch="main",
        base_sha="b" * 40,
        head_sha="a" * 40,
        state="open",
        is_merged=False,
        created_at="2026-08-18T10:00:00Z",
        updated_at="2026-08-18T10:00:00Z",
    )
    requirement = Requirement.objects.create(
        repository=repository,
        external_id="AUTH-3",
        source="jira",
        title="Users can authenticate",
    )
    commit = Commit.objects.create(
        repository=repository,
        pull_request=pull_request,
        sha="c" * 40,
        message="Refactor authentication service",
        author="kilel",
        committed_at="2026-08-18T10:00:00Z",
    )
    changed_file = ChangedFile.objects.create(
        commit=commit,
        filename="auth/service.py",
        status="modified",
    )
    evidence = Evidence.objects.create(
        requirement=requirement,
        pull_request=pull_request,
        commit=commit,
        changed_file=changed_file,
        evidence_type="code",
        status="stale",
    )
    verification = Verification.objects.create(
        requirement=requirement,
        pull_request=pull_request,
        status="stale",
    )
    VerificationEvidence.objects.create(
        verification=verification,
        evidence=evidence,
    )
    EvidenceInvalidation.objects.create(
        evidence=evidence,
        triggering_changed_file=changed_file,
        reason="A newer revision changed auth/service.py.",
    )
    run = VerificationRun.objects.create(
        verification=verification,
        triggering_changed_file=changed_file,
        reason="PR #517 changed auth/service.py.",
    )
    decision = DeliveryDecision.objects.create(
        verification=verification,
        status="stale",
        summary="The verification is stale.",
        rationale={"stale_evidence_ids": [evidence.id]},
    )

    client = APIClient()
    client.force_authenticate(user=user)
    verification_response = client.get(
        reverse("verification-list"),
        {"repository": repository.id, "status": "stale"},
    )
    evidence_response = client.get(
        reverse("evidence-list"),
        {"repository": repository.id, "status": "stale"},
    )
    run_response = client.get(
        reverse("verification-run-list"),
        {"repository": repository.id, "status": "queued"},
    )

    assert verification_response.status_code == 200
    assert verification_response.json()[0]["id"] == verification.id
    assert verification_response.json()[0]["evidence_ids"] == [evidence.id]
    assert verification_response.json()[0]["evidence"][0]["commit_sha"] == (
        commit.sha
    )
    assert verification_response.json()[0]["decision_history"][0]["id"] == (
        decision.id
    )

    assert evidence_response.status_code == 200
    assert evidence_response.json()[0]["id"] == evidence.id
    assert evidence_response.json()[0]["invalidation_history"][0]["reason"] == (
        "A newer revision changed auth/service.py."
    )

    assert run_response.status_code == 200
    assert run_response.json()[0]["id"] == run.id
    assert run_response.json()[0]["verification"] == verification.id

    decision_response = client.get(
        reverse("delivery-decision-list"),
        {"repository": repository.id},
    )
    assert decision_response.status_code == 200
    assert decision_response.json()[0]["id"] == decision.id
    assert decision_response.json()[0]["verification_status"] == "stale"
    assert decision_response.json()[0]["evidence_ids"] == [evidence.id]
    assert decision_response.json()[0]["decision_history"][0]["id"] == decision.id


@pytest.mark.django_db
def test_verification_detail_includes_requirement_and_pull_request_data():
    user = get_user_model().objects.create_user(
        username="verification-detail-reader",
        password="test-password",
    )
    repository = Repository.objects.create(
        github_id=765432,
        owner="aci",
        name="detail-repo",
        full_name="aci/detail-repo",
    )
    repository.members.add(user)
    pull_request = PullRequest.objects.create(
        repository=repository,
        github_id=654321,
        number=9,
        title="Add health check endpoint",
        author="kilel",
        source_branch="feature/health",
        target_branch="main",
        base_sha="b" * 40,
        head_sha="a" * 40,
        state="open",
        is_merged=False,
        created_at="2026-08-18T10:00:00Z",
        updated_at="2026-08-18T10:00:00Z",
    )
    requirement = Requirement.objects.create(
        repository=repository,
        external_id="KIL-3",
        source="jira",
        title="KIL-3 Add health check endpoint",
    )
    verification = Verification.objects.create(
        requirement=requirement,
        pull_request=pull_request,
        status="pending",
    )

    client = APIClient()
    client.force_authenticate(user=user)
    response = client.get(reverse("verification-detail", kwargs={"pk": verification.pk}))

    assert response.status_code == 200
    assert response.json()["requirement"]["external_id"] == "KIL-3"
    assert response.json()["requirement"]["title"] == "KIL-3 Add health check endpoint"
    assert response.json()["pull_request"]["number"] == 9


@pytest.mark.django_db
def test_verification_detail_exposes_ordered_criteria_with_evidence():
    user = get_user_model().objects.create_user(
        username="verification-criteria-reader",
        password="test-password",
    )
    repository = Repository.objects.create(
        github_id=889900,
        owner="aci",
        name="criteria-repo",
        full_name="aci/criteria-repo",
    )
    repository.members.add(user)
    pull_request = PullRequest.objects.create(
        repository=repository,
        github_id=332211,
        number=22,
        title="Ship health endpoint",
        author="kilel",
        source_branch="feature/health",
        target_branch="main",
        base_sha="b" * 40,
        head_sha="a" * 40,
        state="open",
        is_merged=False,
        created_at="2026-08-18T10:00:00Z",
        updated_at="2026-08-18T10:00:00Z",
    )
    requirement = Requirement.objects.create(
        repository=repository,
        external_id="KIL-5",
        source="jira",
        title="Health endpoint",
    )
    criterion_1 = RequirementCriterion.objects.create(
        requirement=requirement,
        text="Health endpoint returns status 200.",
        order=0,
    )
    criterion_2 = RequirementCriterion.objects.create(
        requirement=requirement,
        text="Health check is covered by tests.",
        order=1,
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
        status="valid",
        description="Health route implementation",
        metadata={"filename": "health.py"},
    )
    VerificationEvidence.objects.create(
        verification=verification,
        evidence=evidence,
    )
    first_result = CriterionVerification.objects.create(
        verification=verification,
        criterion=criterion_1,
        status="satisfied",
        summary="Endpoint exists and returns a successful payload.",
        confidence=0.9,
        metadata={"evidence_count": 1},
    )
    CriterionVerification.objects.create(
        verification=verification,
        criterion=criterion_2,
        status="missing",
        summary="No test evidence found for this criterion.",
        confidence=0.0,
        metadata={"evidence_count": 0},
    )
    CriterionVerificationEvidence.objects.create(
        criterion_verification=first_result,
        evidence=evidence,
    )

    client = APIClient()
    client.force_authenticate(user=user)
    response = client.get(reverse("verification-detail", kwargs={"pk": verification.pk}))

    assert response.status_code == 200
    criteria = response.json()["criteria_evaluations"]
    assert [item["criterion_text"] for item in criteria] == [
        criterion_1.text,
        criterion_2.text,
    ]
    assert criteria[0]["status"] == "satisfied"
    assert criteria[0]["evidence"][0]["description"] == "Health route implementation"
    assert criteria[1]["status"] == "missing"


@pytest.mark.django_db
def test_verification_detail_renders_requirement_criteria_even_before_results_exist():
    user = get_user_model().objects.create_user(
        username="verification-criteria-placeholder",
        password="test-password",
    )
    repository = Repository.objects.create(
        github_id=112233,
        owner="aci",
        name="placeholder-repo",
        full_name="aci/placeholder-repo",
    )
    repository.members.add(user)
    pull_request = PullRequest.objects.create(
        repository=repository,
        github_id=445566,
        number=30,
        title="Add login endpoint",
        author="kilel",
        source_branch="feature/login",
        target_branch="main",
        base_sha="b" * 40,
        head_sha="a" * 40,
        state="open",
        is_merged=False,
        created_at="2026-08-18T10:00:00Z",
        updated_at="2026-08-18T10:00:00Z",
    )
    requirement = Requirement.objects.create(
        repository=repository,
        external_id="KIL-4",
        source="jira",
        title="KIL-4 Add login endpoint",
        description=(
            "Add a token-based login endpoint for the API using Django REST Framework. "
            "Acceptance criteria: 1. POST /api/login accepts email and password. "
            "2. Valid credentials return HTTP 200 with a token. "
            "3. Invalid credentials return HTTP 401."
        ),
    )
    verification = Verification.objects.create(
        requirement=requirement,
        pull_request=pull_request,
        status="pending",
    )
    RequirementCriterion.objects.create(
        requirement=requirement,
        text=(
            "{'type': 'doc', 'content': [{'type': 'paragraph', 'content': [{'type': 'text', "
            "'text': 'POST /api/login accepts email and password.'}]}], 'attrs': {'localId': 'bad'}}"
        ),
        order=0,
    )
    RequirementCriterion.objects.create(
        requirement=requirement,
        text="POST /api/login accepts email and password.",
        order=1,
    )
    RequirementCriterion.objects.create(
        requirement=requirement,
        text="Valid credentials return HTTP 200 with a token.",
        order=2,
    )
    RequirementCriterion.objects.create(
        requirement=requirement,
        text="Invalid credentials return HTTP 401.",
        order=3,
    )

    client = APIClient()
    client.force_authenticate(user=user)
    response = client.get(reverse("verification-detail", kwargs={"pk": verification.pk}))

    assert response.status_code == 200
    criteria = response.json()["criteria_evaluations"]
    assert [item["criterion_text"] for item in criteria] == [
        "POST /api/login accepts email and password.",
        "Valid credentials return HTTP 200 with a token.",
        "Invalid credentials return HTTP 401.",
    ]
    assert all(item["status"] == "missing" for item in criteria)


@pytest.mark.django_db
def test_verification_worker_can_process_queued_runs():
    user = get_user_model().objects.create_user(
        username="verification-worker",
        password="test-password",
    )
    repository = Repository.objects.create(
        github_id=998877,
        owner="aci",
        name="worker-repo",
        full_name="aci/worker-repo",
    )
    repository.members.add(user)
    pull_request = PullRequest.objects.create(
        repository=repository,
        github_id=1234567,
        number=28,
        title="Refactor validation",
        author="kilel",
        source_branch="feature/validation",
        target_branch="main",
        base_sha="b" * 40,
        head_sha="a" * 40,
        state="open",
        is_merged=False,
        created_at="2026-08-18T10:00:00Z",
        updated_at="2026-08-18T10:00:00Z",
    )
    requirement = Requirement.objects.create(
        repository=repository,
        external_id="VALID-9",
        source="jira",
        title="Validation is resilient",
    )
    commit = Commit.objects.create(
        repository=repository,
        pull_request=pull_request,
        sha="d" * 40,
        message="Refactor validation logic",
        author="kilel",
        committed_at="2026-08-18T10:35:00Z",
    )
    changed_file = ChangedFile.objects.create(
        commit=commit,
        filename="validation/service.py",
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
        reason="Stale evidence needs a fresh read.",
    )

    client = APIClient()
    client.force_authenticate(user=user)
    response = client.post(
        reverse("verification-process-queued"),
        {"limit": 1},
        format="json",
    )

    assert response.status_code == 200
    assert response.json()["processed"] == 1
    assert response.json()["run_ids"] == [run.id]

    run.refresh_from_db()
    assert run.status == "completed"
    verification.refresh_from_db()
    assert verification.status in {"verified", "partial", "unverified"}
