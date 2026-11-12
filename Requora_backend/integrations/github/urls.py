from django.urls import path

from Requora_backend.integrations.github.webhooks import github_webhook

urlpatterns = [
    path(
        "webhooks/github/",
        github_webhook,
        name="github-webhook",
    ),
]