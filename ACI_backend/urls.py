"""
URL configuration for ACI_backend project.

The `urlpatterns` list routes URLs to views. For more information please see:
    https://docs.djangoproject.com/en/5.2/topics/http/urls/
Examples:
Function views
    1. Add an import:  from my_app import views
    2. Add a URL to urlpatterns:  path('', views.home, name='home')
Class-based views
    1. Add an import:  from other_app.views import Home
    2. Add a URL to urlpatterns:  path('', Home.as_view(), name='home')
Including another URLconf
    1. Import the include() function: from django.urls import include, path
    2. Add a URL to urlpatterns:  path('blog/', include('blog.urls'))
"""
from django.contrib import admin
from django.urls import path, include

from ACI_backend.ACIApp.views import health_check
from ACI_backend.integrations.github.webhooks import github_webhook

urlpatterns = [
    path('admin/', admin.site.urls),
    path("health/", health_check, name="health-check"),
    path("health", health_check, name="health-check-no-slash"),
    path(
        "api/",
        include("ACI_backend.api.urls"),
    ),
    # Accept both slash forms so GitHub webhooks are not 301-redirected
    # (redirects often become GET and then hit our 405).
    path(
        "api/webhooks/github/",
        github_webhook,
        name="github-webhook",
    ),
    path(
        "api/webhooks/github",
        github_webhook,
        name="github-webhook-no-slash",
    ),
]
