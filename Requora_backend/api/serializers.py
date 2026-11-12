import re

from rest_framework import serializers

from Requora_backend.RequoraApp.models import (
    ChangedFile,
    Commit,
    CriterionVerification,
    DeliveryDecision,
    Evidence,
    EvidenceInvalidation,
    PullRequest,
    Repository,
    Requirement,
    TestExecution,
    Verification,
    VerificationEvidence,
    VerificationRun,
)
from Requora_backend.integrations.verification.criteria import (
    rank_criterion_evidence,
    sync_requirement_criteria_from_text,
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


class CriterionVerificationSerializer(serializers.ModelSerializer):
    criterion_text = serializers.CharField(source="criterion.text", read_only=True)
    criterion_category = serializers.CharField(source="criterion.category", read_only=True)
    evidence = serializers.SerializerMethodField()
    evidence_count = serializers.SerializerMethodField()
    related_evidence_count = serializers.SerializerMethodField()

    class Meta:
        model = CriterionVerification
        fields = [
            "id",
            "criterion",
            "criterion_text",
            "criterion_category",
            "status",
            "summary",
            "confidence",
            "metadata",
            "evaluated_at",
            "evidence",
            "evidence_count",
            "related_evidence_count",
        ]
        read_only_fields = fields

    @staticmethod
    def _ranked_evidence(obj):
        if not hasattr(obj, "_ranked_evidence_cache"):
            evidence = [
                link.evidence
                for link in obj.evidence_links.all()
            ]
            obj._ranked_evidence_cache = rank_criterion_evidence(
                criterion=obj.criterion,
                evidence=evidence,
            )
        return obj._ranked_evidence_cache

    def get_evidence(self, obj):
        if not self.context.get("include_criterion_evidence", False):
            return []
        evidence = self._ranked_evidence(obj)[:1]
        return [
            EvidenceSerializer(item).data
            for item in evidence
        ]

    def get_evidence_count(self, obj):
        if not self.context.get("include_criterion_evidence", False):
            return int((obj.metadata or {}).get("evidence_count", 0))
        return len(self._ranked_evidence(obj))

    def get_related_evidence_count(self, obj):
        if not self.context.get("include_criterion_evidence", False):
            return 0
        return max(0, len(self._ranked_evidence(obj)) - 1)


class VerificationSerializer(serializers.ModelSerializer):
    requirement = RequirementSerializer(read_only=True)
    pull_request = PullRequestSerializer(read_only=True)
    evidence_ids = serializers.SerializerMethodField()
    evidence = serializers.SerializerMethodField()
    decision_history = serializers.SerializerMethodField()
    criteria_evaluations = serializers.SerializerMethodField()
    evidence_count = serializers.SerializerMethodField()

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
            "evidence_count",
            "evidence",
            "criteria_evaluations",
            "decision_history",
        ]
        read_only_fields = fields

    def get_evidence_ids(self, verification):
        return [
            link.evidence_id
            for link in verification.evidence_links.all()
        ]

    def get_evidence_count(self, verification):
        if hasattr(verification, "_prefetched_objects_cache") and (
            "evidence_links" in verification._prefetched_objects_cache
        ):
            return len(verification.evidence_links.all())
        return verification.evidence_links.count()

    def get_evidence(self, verification):
        if "evidence_links" in getattr(
            verification,
            "_prefetched_objects_cache",
            {},
        ):
            evidence = [
                link.evidence
                for link in verification.evidence_links.all()[:3]
            ]
        else:
            evidence = Evidence.objects.filter(
                verification_links__verification=verification,
            ).select_related(
                "changed_file",
                "commit",
            ).prefetch_related(
                "invalidations__triggering_changed_file",
            ).order_by("id")[:3]
        return EvidenceSerializer(evidence, many=True).data

    def get_criteria_evaluations(self, verification):
        raw_criteria = [
            criterion
            for criterion in verification.requirement.criteria.all()
            if (
                criterion.is_active
                and not criterion.text.startswith("{")
                and "'type':" not in criterion.text
                and "'content':" not in criterion.text
                and "localId" not in criterion.text
            )
        ]

        seen = set()
        criteria = []
        for criterion in raw_criteria:
            key = re.sub(r"\s+", " ", (criterion.text or "").strip().lower())
            key = key.replace("/", "")
            key = re.sub(r"[^a-z0-9 ]+", "", key)
            if not key or key in seen:
                continue
            seen.add(key)
            criteria.append(criterion)

        result_by_criterion = {
            result.criterion_id: result
            for result in verification.criterion_results.all()
        }

        serialized = []
        for criterion in criteria:
            result = result_by_criterion.get(criterion.id)
            if result is not None:
                serialized.append(
                    CriterionVerificationSerializer(
                        result,
                        context=self.context,
                    ).data
                )
                continue

            serialized.append({
                "id": None,
                "criterion": criterion.id,
                "criterion_text": criterion.text,
                "criterion_category": criterion.category,
                "status": "missing",
                "summary": "No evidence has been recorded for this criterion yet.",
                "confidence": 0.0,
                "metadata": {"evidence_count": 0},
                "evaluated_at": None,
                "evidence": [],
            })

        return serialized

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
