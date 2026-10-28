from django.conf import settings
from django.db import models


class GitHubAccount(models.Model):
    user = models.OneToOneField(
        settings.AUTH_USER_MODEL,
        on_delete=models.CASCADE,
        related_name="github_account",
    )
    github_id = models.BigIntegerField(unique=True)
    github_login = models.CharField(max_length=255)
    connected_at = models.DateTimeField(auto_now=True)

    def __str__(self):
        return f"{self.github_login} ({self.user})"


class Repository(models.Model):
    """A GitHub repository connected to ACI."""

    github_id = models.BigIntegerField(unique=True)

    owner = models.CharField(max_length=255)
    name = models.CharField(max_length=255)

    full_name = models.CharField(
        max_length=512,
        unique=True,
    )

    default_branch = models.CharField(
        max_length=255,
        default="main",
    )

    github_installation_id = models.PositiveBigIntegerField(
        null=True,
        blank=True,
    )

    is_active = models.BooleanField(default=True)

    members = models.ManyToManyField(
        settings.AUTH_USER_MODEL,
        related_name="aci_repositories",
        blank=True,
    )

    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    def __str__(self):
        return self.full_name


class PullRequest(models.Model):
    """A GitHub pull request that ACI needs to analyze."""

    repository = models.ForeignKey(
        Repository,
        on_delete=models.CASCADE,
        related_name="pull_requests",
    )

    github_id = models.BigIntegerField()

    number = models.PositiveIntegerField()

    title = models.CharField(max_length=500)

    author = models.CharField(max_length=255)

    source_branch = models.CharField(max_length=255)
    target_branch = models.CharField(max_length=255)

    base_sha = models.CharField(max_length=40)
    head_sha = models.CharField(max_length=40)

    state = models.CharField(
        max_length=20,
        default="open",
    )

    is_merged = models.BooleanField(default=False)
    aci_comment_id = models.PositiveBigIntegerField(null=True, blank=True)
    aci_comment_hash = models.CharField(max_length=64, blank=True)

    created_at = models.DateTimeField()
    updated_at = models.DateTimeField()

    received_at = models.DateTimeField(
        auto_now_add=True,
    )

    class Meta:
        constraints = [
            models.UniqueConstraint(
                fields=["repository", "number"],
                name="unique_repository_pull_request",
            ),
        ]

        indexes = [
            models.Index(
                fields=["repository", "state"],
            ),
            models.Index(
                fields=["head_sha"],
            ),
        ]

    def __str__(self):
        return f"{self.repository.full_name}#{self.number}"

class Commit(models.Model):
    """A Git commit associated with a pull request."""

    repository = models.ForeignKey(
        Repository,
        on_delete=models.CASCADE,
        related_name="commits",
    )

    pull_request = models.ForeignKey(
        PullRequest,
        on_delete=models.CASCADE,
        related_name="commits",
        null=True,
        blank=True,
    )

    sha = models.CharField(
        max_length=40,
        unique=True,
    )

    message = models.TextField()

    author = models.CharField(max_length=255)

    committed_at = models.DateTimeField()

    created_at = models.DateTimeField(
        auto_now_add=True,
    )

    def __str__(self):
        return self.sha

class ChangedFile(models.Model):
    commit = models.ForeignKey(
        Commit,
        on_delete=models.CASCADE,
        related_name="changed_files",
    )

    filename = models.CharField(max_length=1024)

    status = models.CharField(max_length=50)

    additions = models.PositiveIntegerField(default=0)

    deletions = models.PositiveIntegerField(default=0)

    changes = models.PositiveIntegerField(default=0)

    patch = models.TextField(blank=True)

    created_at = models.DateTimeField(auto_now_add=True)

    def __str__(self):
        return self.filename

class Requirement(models.Model):
    SOURCE_CHOICES = [
        ("jira", "Jira"),
        ("linear", "Linear"),
        ("github", "GitHub"),
        ("manual", "Manual"),
    ]

    STATUS_CHOICES = [
        ("open", "Open"),
        ("in_progress", "In Progress"),
        ("completed", "Completed"),
        ("cancelled", "Cancelled"),
    ]

    repository = models.ForeignKey(
        Repository,
        on_delete=models.CASCADE,
        related_name="requirements",
    )

    external_id = models.CharField(max_length=255)
    source = models.CharField(
        max_length=50,
        choices=SOURCE_CHOICES,
        default="jira",
    )

    title = models.CharField(max_length=500)

    description = models.TextField(blank=True)

    url = models.URLField(blank=True)

    status = models.CharField(
        max_length=30,
        choices=STATUS_CHOICES,
        default="open",
    )

    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        constraints = [
            models.UniqueConstraint(
                fields=["repository", "source", "external_id"],
                name="unique_requirement_source_external_id",
            ),
        ]

    def __str__(self):
        return f"{self.source}:{self.external_id} - {self.title}"

class RequirementPullRequest(models.Model):
    requirement = models.ForeignKey(
        Requirement,
        on_delete=models.CASCADE,
        related_name="pull_request_links",
    )

    pull_request = models.ForeignKey(
        PullRequest,
        on_delete=models.CASCADE,
        related_name="requirement_links",
    )

    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        constraints = [
            models.UniqueConstraint(
                fields=["requirement", "pull_request"],
                name="unique_requirement_pull_request",
            ),
        ]

    def __str__(self):
        return (
            f"{self.requirement} -> "
            f"{self.pull_request}"
        )


class RequirementCriterion(models.Model):
    """A testable expectation derived from a requirement."""

    CATEGORY_CHOICES = [
        ("behavior", "Behavior"),
        ("implementation", "Implementation"),
        ("test", "Test"),
        ("integration", "Integration"),
        ("data", "Data"),
        ("security", "Security"),
        ("configuration", "Configuration"),
    ]

    requirement = models.ForeignKey(
        Requirement,
        on_delete=models.CASCADE,
        related_name="criteria",
    )

    text = models.TextField()
    category = models.CharField(
        max_length=30,
        choices=CATEGORY_CHOICES,
        default="behavior",
    )
    priority = models.PositiveSmallIntegerField(default=0)
    required = models.BooleanField(default=True)
    order = models.PositiveIntegerField(default=0)
    is_active = models.BooleanField(default=True)

    # Examples: path patterns, symbols, test expectations, API contracts, and
    # negative expectations. The schema stays provider-independent.
    expectations = models.JSONField(default=dict, blank=True)

    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        ordering = ["order", "id"]
        indexes = [
            models.Index(fields=["requirement", "is_active", "order"]),
        ]

    def __str__(self):
        return f"{self.requirement} - {self.text[:80]}"


class Evidence(models.Model):
    TYPE_CHOICES = [
        ("code", "Code"),
        ("test", "Test"),
        ("ci", "CI"),
        ("runtime", "Runtime"),
    ]

    STATUS_CHOICES = [
        ("valid", "Valid"),
        ("stale", "Stale"),
        ("invalid", "Invalid"),
    ]

    requirement = models.ForeignKey(
        Requirement,
        on_delete=models.CASCADE,
        related_name="evidence",
    )

    pull_request = models.ForeignKey(
        PullRequest,
        on_delete=models.CASCADE,
        related_name="evidence",
        null=True,
        blank=True,
    )

    commit = models.ForeignKey(
        Commit,
        on_delete=models.CASCADE,
        related_name="evidence",
        null=True,
        blank=True,
    )

    changed_file = models.ForeignKey(
        ChangedFile,
        on_delete=models.CASCADE,
        related_name="evidence",
        null=True,
        blank=True,
    )

    evidence_type = models.CharField(
        max_length=30,
        choices=TYPE_CHOICES,
    )

    status = models.CharField(
        max_length=20,
        choices=STATUS_CHOICES,
        default="valid",
    )

    description = models.TextField(blank=True)

    metadata = models.JSONField(
        default=dict,
        blank=True,
    )

    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    def __str__(self):
        return (
            f"{self.requirement} - "
            f"{self.evidence_type}"
        )


class EvidenceInvalidation(models.Model):
    """An auditable record that a change made evidence no longer current."""

    evidence = models.ForeignKey(
        Evidence,
        on_delete=models.CASCADE,
        related_name="invalidations",
    )

    triggering_changed_file = models.ForeignKey(
        ChangedFile,
        on_delete=models.CASCADE,
        related_name="triggered_invalidations",
    )

    reason = models.CharField(max_length=255)

    invalidated_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        constraints = [
            models.UniqueConstraint(
                fields=["evidence", "triggering_changed_file"],
                name="unique_evidence_invalidation_trigger",
            ),
        ]

    def __str__(self):
        return (
            f"Evidence {self.evidence_id} invalidated by "
            f"{self.triggering_changed_file.filename}"
        )


class Verification(models.Model):
    STATUS_CHOICES = [
        ("pending", "Pending"),
        ("verified", "Verified"),
        ("partial", "Partial"),
        ("unverified", "Unverified"),
        ("stale", "Stale"),
        ("failed", "Failed"),
    ]

    requirement = models.ForeignKey(
        Requirement,
        on_delete=models.CASCADE,
        related_name="verifications",
    )

    pull_request = models.ForeignKey(
        PullRequest,
        on_delete=models.CASCADE,
        related_name="verifications",
        null=True,
        blank=True,
    )

    status = models.CharField(
        max_length=20,
        choices=STATUS_CHOICES,
        default="pending",
    )

    summary = models.TextField(blank=True)

    confidence = models.DecimalField(
        max_digits=5,
        decimal_places=2,
        null=True,
        blank=True,
    )

    verified_at = models.DateTimeField(
        null=True,
        blank=True,
    )

    invalidated_at = models.DateTimeField(
        null=True,
        blank=True,
    )

    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        constraints = [
            models.UniqueConstraint(
                fields=["requirement", "pull_request"],
                name="unique_requirement_pull_request_verification",
            ),
        ]

    def __str__(self):
        return (
            f"{self.requirement} - "
            f"{self.status}"
        )

class VerificationEvidence(models.Model):
    verification = models.ForeignKey(
        Verification,
        on_delete=models.CASCADE,
        related_name="evidence_links",
    )

    evidence = models.ForeignKey(
        Evidence,
        on_delete=models.CASCADE,
        related_name="verification_links",
    )

    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        constraints = [
            models.UniqueConstraint(
                fields=["verification", "evidence"],
                name="unique_verification_evidence",
            ),
        ]


class CriterionVerification(models.Model):
    """An auditable evaluation of one criterion within a verification."""

    STATUS_CHOICES = [
        ("pending", "Pending"),
        ("satisfied", "Satisfied"),
        ("partial", "Partial"),
        ("missing", "Missing"),
        ("not_applicable", "Not Applicable"),
        ("failed", "Failed"),
    ]

    verification = models.ForeignKey(
        Verification,
        on_delete=models.CASCADE,
        related_name="criterion_results",
    )
    criterion = models.ForeignKey(
        RequirementCriterion,
        on_delete=models.CASCADE,
        related_name="verification_results",
    )
    status = models.CharField(
        max_length=20,
        choices=STATUS_CHOICES,
        default="pending",
    )
    summary = models.TextField(blank=True)
    confidence = models.DecimalField(
        max_digits=5,
        decimal_places=2,
        null=True,
        blank=True,
    )
    metadata = models.JSONField(default=dict, blank=True)
    evaluated_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ["evaluated_at", "id"]
        indexes = [
            models.Index(fields=["verification", "criterion"]),
        ]

    def __str__(self):
        return f"Criterion {self.criterion_id} - {self.status}"


class CriterionVerificationEvidence(models.Model):
    """Evidence used for a specific criterion evaluation."""

    criterion_verification = models.ForeignKey(
        CriterionVerification,
        on_delete=models.CASCADE,
        related_name="evidence_links",
    )
    evidence = models.ForeignKey(
        Evidence,
        on_delete=models.CASCADE,
        related_name="criterion_verification_links",
    )
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        constraints = [
            models.UniqueConstraint(
                fields=["criterion_verification", "evidence"],
                name="unique_criterion_verification_evidence",
            ),
        ]


class DeliveryDecision(models.Model):
    """An explainable delivery conclusion derived from a verification."""

    STATUS_CHOICES = [
        ("verified", "Verified"),
        ("partial", "Partial"),
        ("unverified", "Unverified"),
        ("stale", "Stale"),
        ("failed", "Failed"),
    ]

    verification = models.ForeignKey(
        Verification,
        on_delete=models.CASCADE,
        related_name="decisions",
    )
    status = models.CharField(max_length=20, choices=STATUS_CHOICES)
    summary = models.TextField(blank=True)
    confidence = models.DecimalField(
        max_digits=5,
        decimal_places=2,
        null=True,
        blank=True,
    )
    # A compact, immutable explanation snapshot, including missing criteria.
    rationale = models.JSONField(default=dict, blank=True)
    is_current = models.BooleanField(default=True)
    decided_at = models.DateTimeField(auto_now_add=True)
    invalidated_at = models.DateTimeField(null=True, blank=True)
    superseded_at = models.DateTimeField(null=True, blank=True)

    class Meta:
        constraints = [
            models.UniqueConstraint(
                fields=["verification"],
                condition=models.Q(is_current=True),
                name="unique_current_delivery_decision",
            ),
        ]
        indexes = [
            models.Index(fields=["verification", "status"]),
        ]

    def __str__(self):
        return f"Verification {self.verification_id} - {self.status}"


class VerificationRun(models.Model):
    """A queued or completed attempt to re-establish a verification."""

    STATUS_CHOICES = [
        ("queued", "Queued"),
        ("running", "Running"),
        ("completed", "Completed"),
        ("failed", "Failed"),
        ("cancelled", "Cancelled"),
    ]

    verification = models.ForeignKey(
        Verification,
        on_delete=models.CASCADE,
        related_name="runs",
    )

    triggering_changed_file = models.ForeignKey(
        ChangedFile,
        on_delete=models.CASCADE,
        related_name="reverification_runs",
    )

    status = models.CharField(
        max_length=20,
        choices=STATUS_CHOICES,
        default="queued",
    )

    reason = models.CharField(max_length=255)

    requested_at = models.DateTimeField(auto_now_add=True)
    started_at = models.DateTimeField(null=True, blank=True)
    completed_at = models.DateTimeField(null=True, blank=True)

    class Meta:
        constraints = [
            models.UniqueConstraint(
                fields=["verification"],
                condition=models.Q(status__in=["queued", "running"]),
                name="unique_active_verification_run",
            ),
        ]

    def __str__(self):
        return f"Verification {self.verification_id} - {self.status}"


class TestExecution(models.Model):
    """A test command executed as part of a verification run."""

    STATUS_CHOICES = [
        ("pending", "Pending"),
        ("running", "Running"),
        ("passed", "Passed"),
        ("failed", "Failed"),
        ("timed_out", "Timed Out"),
        ("error", "Error"),
    ]

    verification_run = models.ForeignKey(
        VerificationRun,
        on_delete=models.CASCADE,
        related_name="test_executions",
    )

    commit = models.ForeignKey(
        Commit,
        on_delete=models.SET_NULL,
        related_name="test_executions",
        null=True,
        blank=True,
    )

    command = models.JSONField(default=list)
    status = models.CharField(
        max_length=20,
        choices=STATUS_CHOICES,
        default="pending",
    )
    exit_code = models.IntegerField(null=True, blank=True)
    stdout = models.TextField(blank=True)
    stderr = models.TextField(blank=True)
    duration_ms = models.PositiveIntegerField(null=True, blank=True)
    metadata = models.JSONField(default=dict, blank=True)

    started_at = models.DateTimeField(null=True, blank=True)
    completed_at = models.DateTimeField(null=True, blank=True)
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        indexes = [
            models.Index(fields=["verification_run", "status"]),
            models.Index(fields=["commit", "status"]),
        ]

    def __str__(self):
        return f"Test execution {self.pk} - {self.status}"
