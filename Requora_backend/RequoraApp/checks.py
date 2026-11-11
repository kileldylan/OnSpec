from django.conf import settings
from django.core.checks import Warning, register


@register("security", deploy=True)
def require_shared_cache_for_deployment(app_configs=None, **kwargs):
    del app_configs, kwargs
    if settings.DEBUG or settings.REDIS_URL:
        return []
    return [
        Warning(
            "REDIS_URL is unset; API throttling and GitHub token caching "
            "will use process-local memory.",
            hint="Configure a private Redis URL for both the web service and worker.",
            id="requora.W001",
        ),
    ]
