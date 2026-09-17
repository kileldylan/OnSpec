import pytest
from django.contrib.auth import get_user_model
from django.urls import reverse
from rest_framework.test import APIClient

from ACI_backend.ACIApp.models import (
    ChangedFile,
    Commit,
    DeliveryDecision,
    Evidence,
    EvidenceInvalidation,
    PullRequest,
    Repository,
    Requirement,
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
