"""Tenant access helpers for API querysets."""


def visible_repositories(queryset, user, *, membership_path="members"):
    if user.is_superuser:
        return queryset
    return queryset.filter(
        **{membership_path: user},
    ).distinct()