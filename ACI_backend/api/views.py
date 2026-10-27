from django.conf import settings
from rest_framework import status, viewsets
from rest_framework.decorators import action
from rest_framework.response import Response

from ACI_backend.ACIApp.models import (
    DeliveryDecision,
    Evidence,
    PullRequest,
    Repository,
    Requirement,
    RequirementPullRequest,
    TestExecution,
    Verification,
    VerificationRun,
)
from ACI_backend.api.serializers import (
    DeliveryDecisionSerializer,
    EvidenceSerializer,
    PullRequestSerializer,
    RepositorySerializer,
    RequirementSerializer,
    VerificationRunSerializer,
    TestExecutionSerializer,
    VerificationSerializer,
)
from ACI_backend.api.permissions import visible_repositories
from ACI_backend.integrations.jira.client import JiraAPIError, JiraClient
from ACI_backend.integrations.jira.service import ingest_jira_requirement
from ACI_backend.integrations.verification.llm import create_openai_evaluator
from ACI_backend.integrations.verification.service import (
    collect_repository_code_evidence,
    process_next_reverification_run,
    recover_stuck_reverification_runs,
    start_initial_verification,
)


class RepositoryViewSet(viewsets.ModelViewSet):
    serializer_class = RepositorySerializer

    def get_queryset(self):
        return visible_repositories(
            Repository.objects.all(),
            self.request.user,
        )

    def perform_create(self, serializer):
        repository = serializer.save()
        repository.members.add(self.request.user)

    @action(detail=True, methods=["get"], url_path="pull-requests")
    def pull_requests(self, request, pk=None):
        repository = self.get_object()
        pull_requests = repository.pull_requests.order_by("-updated_at", "-id")
        return Response(PullRequestSerializer(pull_requests, many=True).data)

    @action(detail=True, methods=["get"], url_path=r"pull-requests/(?P<pr_pk>[^/.]+)")
    def pull_request_detail(self, request, pk=None, pr_pk=None):
        repository = self.get_object()
        pull_request = repository.pull_requests.filter(pk=pr_pk).first()

        if not pull_request:
            return Response(
                {"detail": "Pull request not found."},
                status=status.HTTP_404_NOT_FOUND,
            )

        # Load commits with changed files
        commits = (
            pull_request.commits
            .prefetch_related("changed_files")
            .order_by("committed_at")
        )

        commits_data = []
        for commit in commits:
            files = [
                {
                    "filename": f.filename,
                    "status": f.status,
                    "additions": f.additions,
                    "deletions": f.deletions,
                    "changes": f.changes,
                    "patch": f.patch,
                }
                for f in commit.changed_files.all()
            ]
            commits_data.append({
                "sha": commit.sha,
                "message": commit.message,
                "author": commit.author,
                "committed_at": commit.committed_at,
                "changed_files": files,
            })

        # Get verifications linked to this PR
        verifications = (
            Verification.objects
            .filter(pull_request=pull_request)
            .select_related("requirement")
            .prefetch_related("evidence_links__evidence")
        )

        data = {
            "pull_request": PullRequestSerializer(pull_request).data,
            "commits": commits_data,
            "verifications": VerificationSerializer(verifications, many=True).data,
        }
        return Response(data)

    @action(detail=True, methods=["get"])
    def requirements(self, request, pk=None):
        repository = self.get_object()
        requirements = repository.requirements.order_by("-updated_at", "-id")
        return Response(RequirementSerializer(requirements, many=True).data)

    @action(detail=True, methods=["post"], url_path="start-verification")
    def start_verification(self, request, pk=None):
        repository = self.get_object()
        pull_request = self._get_pull_request(repository, request.data)
        if pull_request is None:
            return Response(
                {"detail": "A valid pull request id or number is required."},
                status=status.HTTP_400_BAD_REQUEST,
            )
        requirement = self._get_requirement(
            repository,
            request.data,
            pull_request,
        )
        if requirement is None:
            return Response(
                {
                    "detail": (
                        "A requirement id or Jira key is required, and the Jira "
                        "issue must be accessible."
                    ),
                },
                status=status.HTTP_400_BAD_REQUEST,
            )

        RequirementPullRequest.objects.get_or_create(
            requirement=requirement,
            pull_request=pull_request,
        )
        try:
            verification, run = start_initial_verification(
                requirement=requirement,
                pull_request=pull_request,
            )
        except ValueError as error:
            return Response(
                {"detail": str(error)},
                status=status.HTTP_409_CONFLICT,
            )

        return Response(
            {
                "verification": VerificationSerializer(verification).data,
                "run": VerificationRunSerializer(run).data,
            },
            status=status.HTTP_201_CREATED,
        )

    @staticmethod
    def _get_pull_request(repository, data):
        pull_request_id = data.get("pull_request_id")
        pull_request_number = data.get("pull_request_number")
        if pull_request_id is not None:
            return repository.pull_requests.filter(pk=pull_request_id).first()
        if pull_request_number is not None:
            return repository.pull_requests.filter(
                number=pull_request_number,
            ).first()
        return None

    @staticmethod
    def _get_requirement(repository, data, pull_request):
        requirement_id = data.get("requirement_id")
        jira_key = data.get("jira_key")
        if requirement_id is not None:
            return repository.requirements.filter(pk=requirement_id).first()
        if not jira_key:
            return None
        requirement = repository.requirements.filter(
            source="jira",
            external_id=jira_key,
        ).first()
        if requirement is not None:
            return requirement
        try:
            jira_issue = JiraClient().get_issue(jira_key)
        except JiraAPIError:
            return None
        return ingest_jira_requirement(
            pull_request=pull_request,
            jira_issue=jira_issue,
        )


class EvidenceViewSet(viewsets.ReadOnlyModelViewSet):
    serializer_class = EvidenceSerializer

    def get_queryset(self):
        queryset = visible_repositories(
            Evidence.objects.select_related(
            "requirement",
            "pull_request",
            "commit",
            "changed_file",
            ).prefetch_related(
            "invalidations__triggering_changed_file",
            ).order_by("-updated_at"),
            self.request.user,
            membership_path="requirement__repository__members",
        )
        repository_id = self.request.query_params.get("repository")
        requirement_id = self.request.query_params.get("requirement")
        status = self.request.query_params.get("status")
        if repository_id:
            queryset = queryset.filter(requirement__repository_id=repository_id)
        if requirement_id:
            queryset = queryset.filter(requirement_id=requirement_id)
        if status:
            queryset = queryset.filter(status=status)
        return queryset


class VerificationViewSet(viewsets.ReadOnlyModelViewSet):
    serializer_class = VerificationSerializer

    def get_queryset(self):
        queryset = visible_repositories(
            Verification.objects.select_related(
            "requirement",
            "pull_request",
            ).prefetch_related(
            "evidence_links__evidence__invalidations__triggering_changed_file",
            "decisions",
            ).order_by("-created_at"),
            self.request.user,
            membership_path="requirement__repository__members",
        )
        repository_id = self.request.query_params.get("repository")
        requirement_id = self.request.query_params.get("requirement")
        pull_request_id = self.request.query_params.get("pull_request")
        status = self.request.query_params.get("status")
        if repository_id:
            queryset = queryset.filter(requirement__repository_id=repository_id)
        if requirement_id:
            queryset = queryset.filter(requirement_id=requirement_id)
        if pull_request_id:
            queryset = queryset.filter(pull_request_id=pull_request_id)
        if status:
            queryset = queryset.filter(status=status)
        return queryset

    @action(detail=False, methods=["post"], url_path="process-queued")
    def process_queued(self, request):
        limit = request.data.get("limit", 1)
        try:
            limit = int(limit)
        except (TypeError, ValueError):
            return Response(
                {"detail": "limit must be a positive integer."},
                status=status.HTTP_400_BAD_REQUEST,
            )

        if limit < 1:
            return Response(
                {"detail": "limit must be at least 1."},
                status=status.HTTP_400_BAD_REQUEST,
            )

        recover_stuck_reverification_runs()
        processed_run_ids = []
        processed_verification_ids = []

        for _ in range(limit):
            queued_run = VerificationRun.objects.filter(
                status="queued",
            ).order_by("requested_at").first()
            if queued_run is None:
                break

            evaluator = (
                create_openai_evaluator()
                if settings.OPENAI_API_KEY
                else None
            )
            verification = process_next_reverification_run(
                evaluator=evaluator,
                source_evidence_collector=collect_repository_code_evidence,
            )
            if verification is None:
                break

            processed_run_ids.append(queued_run.id)
            processed_verification_ids.append(verification.id)

        return Response(
            {
                "processed": len(processed_run_ids),
                "run_ids": processed_run_ids,
                "verification_ids": processed_verification_ids,
            },
            status=status.HTTP_200_OK,
        )


class VerificationRunViewSet(viewsets.ReadOnlyModelViewSet):
    serializer_class = VerificationRunSerializer

    def get_queryset(self):
        queryset = visible_repositories(
            VerificationRun.objects.select_related(
            "verification",
            "triggering_changed_file",
            ).order_by("-requested_at"),
            self.request.user,
            membership_path="verification__requirement__repository__members",
        )
        repository_id = self.request.query_params.get("repository")
        status = self.request.query_params.get("status")
        if repository_id:
            queryset = queryset.filter(
                verification__requirement__repository_id=repository_id,
            )
        if status:
            queryset = queryset.filter(status=status)
        return queryset


class TestExecutionViewSet(viewsets.ReadOnlyModelViewSet):
    serializer_class = TestExecutionSerializer

    def get_queryset(self):
        queryset = visible_repositories(
            TestExecution.objects.select_related(
            "verification_run",
            "commit",
            ).order_by("-created_at"),
            self.request.user,
            membership_path="verification_run__verification__requirement__repository__members",
        )
        repository_id = self.request.query_params.get("repository")
        status = self.request.query_params.get("status")
        if repository_id:
            queryset = queryset.filter(
                verification_run__verification__requirement__repository_id=(
                    repository_id
                ),
            )
        if status:
            queryset = queryset.filter(status=status)
        return queryset


class DeliveryDecisionViewSet(viewsets.ReadOnlyModelViewSet):
    serializer_class = DeliveryDecisionSerializer

    def get_queryset(self):
        queryset = visible_repositories(
            DeliveryDecision.objects.select_related(
            "verification",
            "verification__requirement",
            "verification__pull_request",
            ).prefetch_related(
            "verification__evidence_links",
            "verification__decisions",
            ).order_by("-decided_at"),
            self.request.user,
            membership_path="verification__requirement__repository__members",
        )
        repository_id = self.request.query_params.get("repository")
        status = self.request.query_params.get("status")
        current = self.request.query_params.get("current")
        if repository_id:
            queryset = queryset.filter(
                verification__requirement__repository_id=repository_id,
            )
        if status:
            queryset = queryset.filter(status=status)
        if current is not None:
            queryset = queryset.filter(is_current=current.lower() == "true")
        return queryset
