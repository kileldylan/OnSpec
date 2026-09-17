from rest_framework import serializers

from ACI_backend.ACIApp.models import (
    ChangedFile,
    Commit,
    DeliveryDecision,
    Evidence,
    EvidenceInvalidation,
    PullRequest,
    Repository,
    Requirement,
    TestExecution,
    Verification,
    VerificationRun,
)


class EvidenceInvalidationSerializer(serializers.ModelSerializer):
    triggering_filename = serializers.CharField(
        source="triggering_changed_file.filename",
        read_only=True,
    )

    class Meta:
        model = EvidenceInvalidation
        fields = [
            "id",
            "triggering_changed_file",
            "triggering_filename",
            "reason",
            "invalidated_at",
        ]
        read_only_fields = fields


class RepositorySerializer(serializers.ModelSerializer):
    class Meta:
        model = Repository
        fields = [
            "id",
            "github_id",
            "owner",
            "name",
            "full_name",
            "default_branch",
            "is_active",
            "members",
            "created_at",
            "updated_at",
        ]

        read_only_fields = [
            "id",
            "created_at",
            "updated_at",
            "members",
        ]


class PullRequestSerializer(serializers.ModelSerializer):
    class Meta:
        model = PullRequest
        fields = [
            "id",
            "repository",
            "github_id",
            "number",
            "title",
            "author",
            "source_branch",
            "target_branch",
            "base_sha",
            "head_sha",
            "state",
            "is_merged",
            "created_at",
            "updated_at",
            "received_at",
        ]
        read_only_fields = fields


class ChangedFileSerializer(serializers.ModelSerializer):
    class Meta:
        model = ChangedFile
        fields = [
            "id",
            "filename",
            "status",
            "additions",
            "deletions",
            "changes",
            "patch",
        ]


class CommitSerializer(serializers.ModelSerializer):
    changed_files = ChangedFileSerializer(many=True, read_only=True)

    class Meta:
        model = Commit
        fields = [
            "id",
            "sha",
            "message",
            "author",
            "committed_at",
            "changed_files",
        ]


class PullRequestDetailSerializer(serializers.ModelSerializer):
    commits = CommitSerializer(many=True, read_only=True)

    class Meta:
        model = PullRequest
        fields = [
            "id",
            "repository",
            "github_id",
            "number",
            "title",
            "author",
            "source_branch",
            "target_branch",
            "base_sha",
            "head_sha",
            "state",
            "is_merged",
            "created_at",
            "updated_at",
            "received_at",
            "commits",
        ]
        read_only_fields = fields


class RequirementSerializer(serializers.ModelSerializer):
    class Meta:
        model = Requirement
        fields = [
            "id",
            "repository",
            "external_id",
            "source",
            "title",
            "description",
            "url",
            "status",
            "created_at",
            "updated_at",
        ]
        read_only_fields = fields


class EvidenceSerializer(serializers.ModelSerializer):
    commit_sha = serializers.CharField(source="commit.sha", read_only=True)
    invalidation_history = EvidenceInvalidationSerializer(
        source="invalidations",
        many=True,
        read_only=True,
    )

    class Meta:
        model = Evidence
        fields = [
            "id",
            "requirement",
            "pull_request",
            "commit",
            "changed_file",
            "commit_sha",
            "evidence_type",
            "status",
            "description",
            "metadata",
            "created_at",
            "updated_at",
            "invalidation_history",
        ]
        read_only_fields = fields


class VerificationSerializer(serializers.ModelSerializer):
    requirement = RequirementSerializer(read_only=True)
    pull_request = PullRequestSerializer(read_only=True)
    evidence_ids = serializers.SerializerMethodField()
    evidence = serializers.SerializerMethodField()
    decision_history = serializers.SerializerMethodField()

    class Meta:
        model = Verification
        fields = [
            "id",
            "requirement",
            "pull_request",
            "status",
            "summary",
            "confidence",
            "verified_at",
            "invalidated_at",
            "created_at",
            "evidence_ids",
            "evidence",
            "decision_history",
        ]
        read_only_fields = fields

    def get_evidence_ids(self, verification):
        return list(
            verification.evidence_links.values_list(
                "evidence_id",
                flat=True,
            )
        )

    def get_evidence(self, verification):
        evidence = Evidence.objects.filter(
            verification_links__verification=verification,
        ).prefetch_related("invalidations__triggering_changed_file")
        return EvidenceSerializer(evidence, many=True).data

    def get_decision_history(self, verification):
        return list(
            verification.decisions.order_by("decided_at", "id").values(
                "id",
                "status",
                "is_current",
                "decided_at",
                "invalidated_at",
                "superseded_at",
            )
        )


class VerificationRunSerializer(serializers.ModelSerializer):
    class Meta:
        model = VerificationRun
        fields = [
            "id",
            "verification",
            "triggering_changed_file",
            "status",
            "reason",
            "requested_at",
            "started_at",
            "completed_at",
        ]
        read_only_fields = fields


class TestExecutionSerializer(serializers.ModelSerializer):
    class Meta:
        model = TestExecution
        fields = [
            "id",
            "verification_run",
            "commit",
            "command",
            "status",
            "exit_code",
            "stdout",
            "stderr",
            "duration_ms",
            "metadata",
            "started_at",
            "completed_at",
            "created_at",
        ]
        read_only_fields = fields


class DeliveryDecisionSerializer(serializers.ModelSerializer):
    verification_status = serializers.CharField(
        source="verification.status",
        read_only=True,
    )
    evidence_ids = serializers.SerializerMethodField()
    decision_history = serializers.SerializerMethodField()

    class Meta:
        model = DeliveryDecision
        fields = [
            "id",
            "verification",
            "verification_status",
            "evidence_ids",
            "status",
            "summary",
            "confidence",
            "rationale",
            "is_current",
            "decided_at",
            "invalidated_at",
            "superseded_at",
            "decision_history",
        ]
        read_only_fields = fields

    def get_evidence_ids(self, decision):
        return list(
            decision.verification.evidence_links.values_list(
                "evidence_id",
                flat=True,
            )
        )

    def get_decision_history(self, decision):
        return list(
            decision.verification.decisions.order_by("decided_at", "id").values(
                "id",
                "status",
                "is_current",
                "decided_at",
                "invalidated_at",
                "superseded_at",
            )
        )
