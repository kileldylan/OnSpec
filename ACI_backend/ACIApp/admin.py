# ACI_backend/ACIApp/admin.py
from django.contrib import admin
from django.utils.html import format_html
from django.urls import reverse
from django.db.models import Count, Q
from .models import (
    Repository,
    PullRequest,
    Commit,
    ChangedFile,
    Requirement,
    RequirementPullRequest,
    RequirementCriterion,
    Evidence,
    EvidenceInvalidation,
    Verification,
    VerificationEvidence,
    CriterionVerification,
    CriterionVerificationEvidence,
    DeliveryDecision,
    VerificationRun,
    TestExecution,
    GitHubWebhookJob,
)


# ============================================================================
# INLINES
# ============================================================================

class CommitInline(admin.TabularInline):
    """Inline commits for a pull request."""
    model = Commit
    fields = ['sha', 'message', 'author', 'committed_at']
    readonly_fields = ['sha', 'message', 'author', 'committed_at']
    extra = 0
    can_delete = False
    max_num = 0
    show_change_link = True


class ChangedFileInline(admin.TabularInline):
    """Inline changed files for a commit."""
    model = ChangedFile
    fields = ['filename', 'status', 'additions', 'deletions', 'changes']
    readonly_fields = ['filename', 'status', 'additions', 'deletions', 'changes']
    extra = 0
    can_delete = False
    max_num = 0
    show_change_link = True


class RequirementCriterionInline(admin.TabularInline):
    """Inline criteria for a requirement."""
    model = RequirementCriterion
    fields = ['text', 'category', 'priority', 'required', 'order', 'is_active']
    extra = 0
    show_change_link = True


class VerificationInline(admin.TabularInline):
    """Inline verifications for a requirement."""
    model = Verification
    fields = ['status', 'confidence', 'summary', 'verified_at']
    readonly_fields = ['created_at']
    extra = 0
    can_delete = False
    max_num = 0
    show_change_link = True
    ordering = ['-created_at']


class EvidenceInline(admin.TabularInline):
    """Inline evidence for a verification."""
    model = VerificationEvidence
    fields = ['evidence', 'created_at']
    readonly_fields = ['created_at']
    extra = 0
    can_delete = False
    max_num = 0


class CriterionVerificationInline(admin.TabularInline):
    """Inline criterion verifications."""
    model = CriterionVerification
    fields = ['criterion', 'status', 'confidence', 'summary']
    readonly_fields = ['evaluated_at']
    extra = 0
    can_delete = False
    show_change_link = True


class DeliveryDecisionInline(admin.TabularInline):
    """Inline delivery decisions for a verification."""
    model = DeliveryDecision
    fields = ['status', 'confidence', 'summary', 'is_current', 'decided_at']
    readonly_fields = ['decided_at']
    extra = 0
    can_delete = False
    max_num = 0
    show_change_link = True


class TestExecutionInline(admin.TabularInline):
    """Inline test executions for a verification run."""
    model = TestExecution
    fields = ['status', 'command', 'exit_code', 'duration_ms', 'started_at', 'completed_at']
    readonly_fields = ['created_at']
    extra = 0
    can_delete = False
    max_num = 0


# ============================================================================
# ADMIN CLASSES
# ============================================================================

@admin.register(Repository)
class RepositoryAdmin(admin.ModelAdmin):
    """Admin for Repository model."""
    list_display = ['id', 'full_name', 'owner', 'default_branch', 'is_active', 'pull_request_count', 'requirement_count']
    list_filter = ['is_active', 'created_at']
    search_fields = ['full_name', 'owner', 'name']
    readonly_fields = ['github_id', 'created_at', 'updated_at']
    fieldsets = (
        ('Basic Information', {
            'fields': ('full_name', 'owner', 'name', 'github_id')
        }),
        ('Configuration', {
            'fields': ('default_branch', 'is_active')
        }),
        ('Timestamps', {
            'fields': ('created_at', 'updated_at'),
            'classes': ('collapse',)
        }),
    )
    
    def get_queryset(self, request):
        return super().get_queryset(request).annotate(
            _pull_request_count=Count('pull_requests'),
            _requirement_count=Count('requirements')
        )
    
    def pull_request_count(self, obj):
        return obj._pull_request_count
    pull_request_count.short_description = 'PRs'
    pull_request_count.admin_order_field = '_pull_request_count'
    
    def requirement_count(self, obj):
        return obj._requirement_count
    requirement_count.short_description = 'Requirements'
    requirement_count.admin_order_field = '_requirement_count'


@admin.register(PullRequest)
class PullRequestAdmin(admin.ModelAdmin):
    """Admin for PullRequest model."""
    list_display = ['id', 'number', 'repository_link', 'title_short', 'author', 'state', 'is_merged', 'verification_status', 'created_at']
    list_filter = ['state', 'is_merged', 'created_at', 'repository']
    search_fields = ['title', 'author', 'source_branch', 'target_branch']
    readonly_fields = ['github_id', 'received_at']
    ordering = ['-created_at']
    inlines = [CommitInline]
    
    def repository_link(self, obj):
        url = reverse('admin:ACIApp_repository_change', args=[obj.repository.id])
        return format_html('<a href="{}">{}</a>', url, obj.repository.full_name)
    repository_link.short_description = 'Repository'
    
    def title_short(self, obj):
        return obj.title[:50] + '...' if len(obj.title) > 50 else obj.title
    title_short.short_description = 'Title'
    
    def verification_status(self, obj):
        verification = obj.verifications.order_by('-created_at').first()
        if verification:
            return format_html(
                '<span style="color: {};">{}</span>',
                'green' if verification.status == 'verified' else
                'orange' if verification.status == 'partial' else
                'red' if verification.status == 'unverified' else 'gray',
                verification.status.upper()
            )
        return '—'
    verification_status.short_description = 'Status'


@admin.register(Commit)
class CommitAdmin(admin.ModelAdmin):
    """Admin for Commit model."""
    list_display = ['id', 'sha_short', 'pull_request_link', 'message_short', 'author', 'committed_at']
    list_filter = ['committed_at', 'repository']
    search_fields = ['sha', 'message', 'author']
    readonly_fields = ['sha', 'committed_at', 'created_at']
    inlines = [ChangedFileInline]
    
    def sha_short(self, obj):
        return obj.sha[:8]
    sha_short.short_description = 'SHA'
    
    def pull_request_link(self, obj):
        if obj.pull_request:
            url = reverse('admin:ACIApp_pullrequest_change', args=[obj.pull_request.id])
            return format_html('<a href="{}">#{}</a>', url, obj.pull_request.number)
        return '—'
    pull_request_link.short_description = 'PR'
    
    def message_short(self, obj):
        return obj.message[:50] + '...' if len(obj.message) > 50 else obj.message
    message_short.short_description = 'Message'


@admin.register(ChangedFile)
class ChangedFileAdmin(admin.ModelAdmin):
    """Admin for ChangedFile model."""
    list_display = ['id', 'filename_short', 'commit_link', 'status', 'additions', 'deletions', 'changes', 'created_at']
    list_filter = ['status', 'created_at']
    search_fields = ['filename']
    readonly_fields = ['created_at']
    
    def filename_short(self, obj):
        return obj.filename[:60] + '...' if len(obj.filename) > 60 else obj.filename
    filename_short.short_description = 'Filename'
    
    def commit_link(self, obj):
        if obj.commit:
            url = reverse('admin:ACIApp_commit_change', args=[obj.commit.id])
            return format_html('<a href="{}">{}</a>', url, obj.commit.sha[:8])
        return '—'
    commit_link.short_description = 'Commit'


@admin.register(Requirement)
class RequirementAdmin(admin.ModelAdmin):
    """Admin for Requirement model."""
    list_display = ['id', 'external_id', 'title_short', 'source', 'repository_link', 'status', 'verification_status', 'created_at']
    list_filter = ['source', 'status', 'created_at', 'repository']
    search_fields = ['external_id', 'title', 'description']
    readonly_fields = ['created_at', 'updated_at']
    inlines = [RequirementCriterionInline, VerificationInline]
    fieldsets = (
        ('Basic Information', {
            'fields': ('repository', 'external_id', 'source', 'title', 'description', 'url')
        }),
        ('Status', {
            'fields': ('status',)
        }),
        ('Timestamps', {
            'fields': ('created_at', 'updated_at'),
            'classes': ('collapse',)
        }),
    )
    
    def repository_link(self, obj):
        url = reverse('admin:ACIApp_repository_change', args=[obj.repository.id])
        return format_html('<a href="{}">{}</a>', url, obj.repository.full_name)
    repository_link.short_description = 'Repository'
    
    def title_short(self, obj):
        return obj.title[:50] + '...' if len(obj.title) > 50 else obj.title
    title_short.short_description = 'Title'
    
    def verification_status(self, obj):
        verification = obj.verifications.order_by('-created_at').first()
        if verification:
            return format_html(
                '<span style="color: {}; font-weight: bold;">{}</span>',
                'green' if verification.status == 'verified' else
                'orange' if verification.status == 'partial' else
                'red' if verification.status == 'unverified' else 'gray',
                verification.status.upper()
            )
        return '—'
    verification_status.short_description = 'Latest Verification'


@admin.register(RequirementCriterion)
class RequirementCriterionAdmin(admin.ModelAdmin):
    """Admin for RequirementCriterion model."""
    list_display = ['id', 'requirement_link', 'text_short', 'category', 'priority', 'required', 'order', 'is_active']
    list_filter = ['category', 'required', 'is_active', 'created_at']
    search_fields = ['text', 'requirement__title', 'requirement__external_id']
    readonly_fields = ['created_at', 'updated_at']
    fieldsets = (
        ('Basic Information', {
            'fields': ('requirement', 'text', 'category')
        }),
        ('Configuration', {
            'fields': ('priority', 'required', 'order', 'is_active')
        }),
        ('Metadata', {
            'fields': ('expectations', 'created_at', 'updated_at'),
            'classes': ('collapse',)
        }),
    )
    
    def requirement_link(self, obj):
        url = reverse('admin:ACIApp_requirement_change', args=[obj.requirement.id])
        return format_html('<a href="{}">{}</a>', url, obj.requirement.external_id)
    requirement_link.short_description = 'Requirement'
    
    def text_short(self, obj):
        return obj.text[:60] + '...' if len(obj.text) > 60 else obj.text
    text_short.short_description = 'Text'


@admin.register(Evidence)
class EvidenceAdmin(admin.ModelAdmin):
    """Admin for Evidence model."""
    list_display = ['id', 'requirement_link', 'pull_request_link', 'evidence_type', 'status', 'created_at']
    list_filter = ['evidence_type', 'status', 'created_at', 'requirement']
    search_fields = ['description', 'metadata']
    readonly_fields = ['created_at', 'updated_at']
    fieldsets = (
        ('Relationships', {
            'fields': ('requirement', 'pull_request', 'commit', 'changed_file')
        }),
        ('Evidence Details', {
            'fields': ('evidence_type', 'status', 'description', 'metadata')
        }),
        ('Timestamps', {
            'fields': ('created_at', 'updated_at'),
            'classes': ('collapse',)
        }),
    )
    
    def requirement_link(self, obj):
        url = reverse('admin:ACIApp_requirement_change', args=[obj.requirement.id])
        return format_html('<a href="{}">{}</a>', url, obj.requirement.external_id)
    requirement_link.short_description = 'Requirement'
    
    def pull_request_link(self, obj):
        if obj.pull_request:
            url = reverse('admin:ACIApp_pullrequest_change', args=[obj.pull_request.id])
            return format_html('<a href="{}">#{}</a>', url, obj.pull_request.number)
        return '—'
    pull_request_link.short_description = 'PR'


@admin.register(Verification)
class VerificationAdmin(admin.ModelAdmin):
    """Admin for Verification model."""
    list_display = ['id', 'requirement_link', 'pull_request_link', 'status_color', 'confidence', 'summary_short', 'created_at']
    list_filter = ['status', 'created_at', 'requirement']
    search_fields = ['summary', 'requirement__title', 'requirement__external_id']
    readonly_fields = ['created_at']
    inlines = [CriterionVerificationInline, DeliveryDecisionInline, EvidenceInline]
    fieldsets = (
        ('Relationships', {
            'fields': ('requirement', 'pull_request')
        }),
        ('Verification Result', {
            'fields': ('status', 'summary', 'confidence')
        }),
        ('Timestamps', {
            'fields': ('verified_at', 'invalidated_at', 'created_at'),
            'classes': ('collapse',)
        }),
    )
    
    def requirement_link(self, obj):
        url = reverse('admin:ACIApp_requirement_change', args=[obj.requirement.id])
        return format_html('<a href="{}">{}</a>', url, obj.requirement.external_id)
    requirement_link.short_description = 'Requirement'
    
    def pull_request_link(self, obj):
        if obj.pull_request:
            url = reverse('admin:ACIApp_pullrequest_change', args=[obj.pull_request.id])
            return format_html('<a href="{}">#{}</a>', url, obj.pull_request.number)
        return '—'
    pull_request_link.short_description = 'PR'
    
    def status_color(self, obj):
        colors = {
            'verified': 'green',
            'partial': 'orange',
            'unverified': 'red',
            'pending': 'gray',
            'failed': 'darkred',
            'stale': '#9966cc',
        }
        return format_html(
            '<span style="color: {}; font-weight: bold;">{}</span>',
            colors.get(obj.status, 'gray'),
            obj.status.upper()
        )
    status_color.short_description = 'Status'
    
    def summary_short(self, obj):
        return obj.summary[:60] + '...' if len(obj.summary) > 60 else obj.summary
    summary_short.short_description = 'Summary'


@admin.register(DeliveryDecision)
class DeliveryDecisionAdmin(admin.ModelAdmin):
    """Admin for DeliveryDecision model."""
    list_display = ['id', 'verification_link', 'status_color', 'confidence', 'summary_short', 'is_current', 'decided_at']
    list_filter = ['status', 'is_current', 'decided_at']
    search_fields = ['summary', 'rationale']
    readonly_fields = ['decided_at']
    fieldsets = (
        ('Relationship', {
            'fields': ('verification',)
        }),
        ('Decision', {
            'fields': ('status', 'summary', 'confidence', 'rationale')
        }),
        ('State', {
            'fields': ('is_current',)
        }),
        ('Timestamps', {
            'fields': ('decided_at', 'invalidated_at', 'superseded_at'),
            'classes': ('collapse',)
        }),
    )
    
    def verification_link(self, obj):
        url = reverse('admin:ACIApp_verification_change', args=[obj.verification.id])
        return format_html('<a href="{}">#{}</a>', url, obj.verification.id)
    verification_link.short_description = 'Verification'
    
    def status_color(self, obj):
        colors = {
            'verified': 'green',
            'partial': 'orange',
            'unverified': 'red',
            'failed': 'darkred',
            'stale': '#9966cc',
        }
        return format_html(
            '<span style="color: {}; font-weight: bold;">{}</span>',
            colors.get(obj.status, 'gray'),
            obj.status.upper()
        )
    status_color.short_description = 'Status'
    
    def summary_short(self, obj):
        return obj.summary[:60] + '...' if len(obj.summary) > 60 else obj.summary
    summary_short.short_description = 'Summary'


@admin.register(VerificationRun)
class VerificationRunAdmin(admin.ModelAdmin):
    """Admin for VerificationRun model."""
    list_display = ['id', 'verification_link', 'status_color', 'reason', 'requested_at', 'duration']
    list_filter = ['status', 'requested_at']
    search_fields = ['reason']
    readonly_fields = ['requested_at']
    inlines = [TestExecutionInline]
    fieldsets = (
        ('Relationship', {
            'fields': ('verification', 'triggering_changed_file')
        }),
        ('Status', {
            'fields': ('status', 'reason')
        }),
        ('Timestamps', {
            'fields': ('requested_at', 'started_at', 'completed_at'),
            'classes': ('collapse',)
        }),
    )
    
    def verification_link(self, obj):
        url = reverse('admin:ACIApp_verification_change', args=[obj.verification.id])
        return format_html('<a href="{}">#{}</a>', url, obj.verification.id)
    verification_link.short_description = 'Verification'
    
    def status_color(self, obj):
        colors = {
            'queued': 'gray',
            'running': 'blue',
            'completed': 'green',
            'failed': 'red',
            'cancelled': 'orange',
        }
        return format_html(
            '<span style="color: {}; font-weight: bold;">{}</span>',
            colors.get(obj.status, 'gray'),
            obj.status.upper()
        )
    status_color.short_description = 'Status'
    
    def duration(self, obj):
        if obj.started_at and obj.completed_at:
            delta = obj.completed_at - obj.started_at
            seconds = delta.total_seconds()
            if seconds < 60:
                return f'{int(seconds)}s'
            elif seconds < 3600:
                return f'{int(seconds // 60)}m {int(seconds % 60)}s'
            else:
                return f'{int(seconds // 3600)}h {int((seconds % 3600) // 60)}m'
        return '—'
    duration.short_description = 'Duration'


@admin.register(GitHubWebhookJob)
class GitHubWebhookJobAdmin(admin.ModelAdmin):
    list_display = (
        "delivery_id",
        "event",
        "status",
        "attempts",
        "received_at",
        "completed_at",
    )
    list_filter = ("event", "status")
    search_fields = ("delivery_id", "last_error")
    readonly_fields = (
        "delivery_id",
        "event",
        "payload",
        "attempts",
        "last_error",
        "received_at",
        "started_at",
        "completed_at",
    )


@admin.register(TestExecution)
class TestExecutionAdmin(admin.ModelAdmin):
    """Admin for TestExecution model."""
    list_display = ['id', 'verification_run_link', 'status_color', 'command_short', 'exit_code', 'duration_ms', 'created_at']
    list_filter = ['status', 'created_at']
    search_fields = ['command', 'stdout', 'stderr']
    readonly_fields = ['created_at']
    fieldsets = (
        ('Relationship', {
            'fields': ('verification_run', 'commit')
        }),
        ('Command', {
            'fields': ('command',)
        }),
        ('Result', {
            'fields': ('status', 'exit_code', 'stdout', 'stderr', 'duration_ms', 'metadata')
        }),
        ('Timestamps', {
            'fields': ('started_at', 'completed_at', 'created_at'),
            'classes': ('collapse',)
        }),
    )
    
    def verification_run_link(self, obj):
        url = reverse('admin:ACIApp_verificationrun_change', args=[obj.verification_run.id])
        return format_html('<a href="{}">#{}</a>', url, obj.verification_run.id)
    verification_run_link.short_description = 'Run'
    
    def status_color(self, obj):
        colors = {
            'pending': 'gray',
            'running': 'blue',
            'passed': 'green',
            'failed': 'red',
            'timed_out': 'orange',
            'error': 'darkred',
        }
        return format_html(
            '<span style="color: {}; font-weight: bold;">{}</span>',
            colors.get(obj.status, 'gray'),
            obj.status.upper()
        )
    status_color.short_description = 'Status'
    
    def command_short(self, obj):
        cmd = ' '.join(obj.command) if isinstance(obj.command, list) else str(obj.command)
        return cmd[:40] + '...' if len(cmd) > 40 else cmd
    command_short.short_description = 'Command'


# ============================================================================
# REGISTER REMAINING MODELS
# ============================================================================

@admin.register(RequirementPullRequest)
class RequirementPullRequestAdmin(admin.ModelAdmin):
    """Admin for RequirementPullRequest junction table."""
    list_display = ['id', 'requirement_link', 'pull_request_link', 'created_at']
    list_filter = ['created_at']
    readonly_fields = ['created_at']
    
    def requirement_link(self, obj):
        url = reverse('admin:ACIApp_requirement_change', args=[obj.requirement.id])
        return format_html('<a href="{}">{}</a>', url, obj.requirement.external_id)
    requirement_link.short_description = 'Requirement'
    
    def pull_request_link(self, obj):
        url = reverse('admin:ACIApp_pullrequest_change', args=[obj.pull_request.id])
        return format_html('<a href="{}">#{}</a>', url, obj.pull_request.number)
    pull_request_link.short_description = 'PR'


@admin.register(EvidenceInvalidation)
class EvidenceInvalidationAdmin(admin.ModelAdmin):
    """Admin for EvidenceInvalidation model."""
    list_display = ['id', 'evidence_link', 'triggering_file', 'reason', 'invalidated_at']
    list_filter = ['invalidated_at']
    search_fields = ['reason']
    readonly_fields = ['invalidated_at']
    
    def evidence_link(self, obj):
        url = reverse('admin:ACIApp_evidence_change', args=[obj.evidence.id])
        return format_html('<a href="{}">#{}</a>', url, obj.evidence.id)
    evidence_link.short_description = 'Evidence'
    
    def triggering_file(self, obj):
        return obj.triggering_changed_file.filename[:50] + '...' if len(obj.triggering_changed_file.filename) > 50 else obj.triggering_changed_file.filename
    triggering_file.short_description = 'Triggering File'


@admin.register(VerificationEvidence)
class VerificationEvidenceAdmin(admin.ModelAdmin):
    """Admin for VerificationEvidence junction table."""
    list_display = ['id', 'verification_link', 'evidence_link', 'created_at']
    list_filter = ['created_at']
    readonly_fields = ['created_at']
    
    def verification_link(self, obj):
        url = reverse('admin:ACIApp_verification_change', args=[obj.verification.id])
        return format_html('<a href="{}">#{}</a>', url, obj.verification.id)
    verification_link.short_description = 'Verification'
    
    def evidence_link(self, obj):
        url = reverse('admin:ACIApp_evidence_change', args=[obj.evidence.id])
        return format_html('<a href="{}">#{}</a>', url, obj.evidence.id)
    evidence_link.short_description = 'Evidence'


@admin.register(CriterionVerification)
class CriterionVerificationAdmin(admin.ModelAdmin):
    """Admin for CriterionVerification model."""
    list_display = ['id', 'verification_link', 'criterion_text_short', 'status', 'confidence', 'evaluated_at']
    list_filter = ['status', 'evaluated_at']
    search_fields = ['summary', 'criterion__text']
    readonly_fields = ['evaluated_at']
    inlines = [admin.TabularInline for _ in []]
    
    def verification_link(self, obj):
        url = reverse('admin:ACIApp_verification_change', args=[obj.verification.id])
        return format_html('<a href="{}">#{}</a>', url, obj.verification.id)
    verification_link.short_description = 'Verification'
    
    def criterion_text_short(self, obj):
        return obj.criterion.text[:50] + '...' if len(obj.criterion.text) > 50 else obj.criterion.text
    criterion_text_short.short_description = 'Criterion'


@admin.register(CriterionVerificationEvidence)
class CriterionVerificationEvidenceAdmin(admin.ModelAdmin):
    """Admin for CriterionVerificationEvidence junction table."""
    list_display = ['id', 'criterion_verification_link', 'evidence_link', 'created_at']
    list_filter = ['created_at']
    readonly_fields = ['created_at']
    
    def criterion_verification_link(self, obj):
        url = reverse('admin:ACIApp_criterionverification_change', args=[obj.criterion_verification.id])
        return format_html('<a href="{}">#{}</a>', url, obj.criterion_verification.id)
    criterion_verification_link.short_description = 'Criterion Verification'
    
    def evidence_link(self, obj):
        url = reverse('admin:ACIApp_evidence_change', args=[obj.evidence.id])
        return format_html('<a href="{}">#{}</a>', url, obj.evidence.id)
    evidence_link.short_description = 'Evidence'