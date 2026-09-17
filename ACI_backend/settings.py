import environ
from pathlib import Path

# =============================================================================
# BASE DIRECTORY
# =============================================================================

BASE_DIR = Path(__file__).resolve().parent.parent
BACKEND_DIR = Path(__file__).resolve().parent

# =============================================================================
# ENVIRONMENT VARIABLES
# =============================================================================

env = environ.Env(
    DEBUG=(bool, False),
    ALLOW_TUNNEL_HOSTS=(bool, False),
)

environ.Env.read_env(BACKEND_DIR / ".env")

# =============================================================================
# SECURITY
# =============================================================================

GITHUB_WEBHOOK_SECRET = env("GITHUB_WEBHOOK_SECRET")
GITHUB_ACCESS_TOKEN = env("GITHUB_ACCESS_TOKEN")
GITHUB_API_TIMEOUT = env.int("GITHUB_API_TIMEOUT", default=15)
JIRA_BASE_URL = env("JIRA_BASE_URL", default="").rstrip("/")
JIRA_EMAIL = env("JIRA_EMAIL", default="")
JIRA_API_TOKEN = env("JIRA_API_TOKEN", default="")
JIRA_API_TIMEOUT = env.int("JIRA_API_TIMEOUT", default=15)
ACI_ENABLE_TEST_EXECUTION = env.bool(
    "ACI_ENABLE_TEST_EXECUTION",
    default=False,
)
ACI_TEST_WORKSPACE = env("ACI_TEST_WORKSPACE", default="")
ACI_TEST_DOCKER_IMAGE = env("ACI_TEST_DOCKER_IMAGE", default="")
GITHUB_TEST_EVIDENCE_CONTEXTS = tuple(
    context.strip()
    for context in env(
        "GITHUB_TEST_EVIDENCE_CONTEXTS",
        default="test,tests,pytest,unit,unit-tests",
    ).split(",")
    if context.strip()
)
GITHUB_CI_EVIDENCE_CONTEXTS = tuple(
    context.strip()
    for context in env(
        "GITHUB_CI_EVIDENCE_CONTEXTS",
        default="build,ci,lint,codeql,security",
    ).split(",")
    if context.strip()
)
LLM_PROVIDER = env("LLM_PROVIDER", default="deterministic")
LLM_MODEL = env("LLM_MODEL", default="gpt-4.1-mini")
OPENAI_API_KEY = env("OPENAI_API_KEY", default="")
SECRET_KEY = env("SECRET_KEY")

DEBUG = env.bool("DEBUG", default=False)

ALLOWED_HOSTS = env.list(
    "ALLOWED_HOSTS",
    default=["localhost", "127.0.0.1"],
)

# Dev tunnels (ngrok / cloudflared). A leading-dot entry is a subdomain wildcard
# in Django, so ".ngrok-free.app" matches "abc123.ngrok-free.app".
# Enabled when DEBUG=True, or when ALLOW_TUNNEL_HOSTS=True (even if DEBUG is off).
ALLOW_TUNNEL_HOSTS = env.bool("ALLOW_TUNNEL_HOSTS", default=DEBUG)
if ALLOW_TUNNEL_HOSTS:
    for tunnel_host in (
        ".ngrok-free.app",
        ".ngrok-free.dev",
        ".ngrok.app",
        ".ngrok.io",
        ".trycloudflare.com",
    ):
        if tunnel_host not in ALLOWED_HOSTS:
            ALLOWED_HOSTS.append(tunnel_host)

# =============================================================================
# APPLICATIONS
# =============================================================================

INSTALLED_APPS = [
    # Django apps
    "django.contrib.admin",
    "django.contrib.auth",
    "django.contrib.contenttypes",
    "django.contrib.sessions",
    "django.contrib.messages",
    "django.contrib.staticfiles",

        "ACI_backend.ACIApp.apps.AciappConfig",
    
    # Third-party
    "rest_framework",

]

# =============================================================================
# MIDDLEWARE
# =============================================================================

MIDDLEWARE = [
    "django.middleware.security.SecurityMiddleware",
    "django.contrib.sessions.middleware.SessionMiddleware",
    "django.middleware.common.CommonMiddleware",
    "django.middleware.csrf.CsrfViewMiddleware",
    "django.contrib.auth.middleware.AuthenticationMiddleware",
    "django.contrib.messages.middleware.MessageMiddleware",
    "django.middleware.clickjacking.XFrameOptionsMiddleware",
]

# =============================================================================
# URLS
# =============================================================================

ROOT_URLCONF = "ACI_backend.urls"

# =============================================================================
# TEMPLATES
# =============================================================================

TEMPLATES = [
    {
        "BACKEND": "django.template.backends.django.DjangoTemplates",
        "DIRS": [],
        "APP_DIRS": True,
        "OPTIONS": {
            "context_processors": [
                "django.template.context_processors.request",
                "django.contrib.auth.context_processors.auth",
                "django.contrib.messages.context_processors.messages",
            ],
        },
    },
]

# =============================================================================
# WSGI / ASGI
# =============================================================================

WSGI_APPLICATION = "ACI_backend.wsgi.application"
ASGI_APPLICATION = "ACI_backend.asgi.application"

# =============================================================================
# DATABASE
# =============================================================================

DATABASES = {
    "default": {
        "ENGINE": "django.db.backends.postgresql",
        "NAME": env("DATABASE_NAME"),
        "USER": env("DATABASE_USER"),
        "PASSWORD": env("DATABASE_PASSWORD"),
        "HOST": env("DATABASE_HOST", default="localhost"),
        "PORT": env("DATABASE_PORT", default="5432"),
    }
}

# =============================================================================
# PASSWORD VALIDATION
# =============================================================================

AUTH_PASSWORD_VALIDATORS = [
    {
        "NAME": "django.contrib.auth.password_validation.UserAttributeSimilarityValidator",
    },
    {
        "NAME": "django.contrib.auth.password_validation.MinimumLengthValidator",
    },
    {
        "NAME": "django.contrib.auth.password_validation.CommonPasswordValidator",
    },
    {
        "NAME": "django.contrib.auth.password_validation.NumericPasswordValidator",
    },
]

# =============================================================================
# INTERNATIONALIZATION
# =============================================================================

LANGUAGE_CODE = "en-us"

TIME_ZONE = "UTC"

USE_I18N = True
USE_TZ = True

# =============================================================================
# STATIC FILES
# =============================================================================

STATIC_URL = "static/"

# =============================================================================
# DEFAULT PRIMARY KEY
# =============================================================================

DEFAULT_AUTO_FIELD = "django.db.models.BigAutoField"

# =============================================================================
# DJANGO REST FRAMEWORK
# =============================================================================

REST_FRAMEWORK = {
    "DEFAULT_PERMISSION_CLASSES": [
        "rest_framework.permissions.IsAuthenticated",
    ],
}

# CSRF Settings
CSRF_TRUSTED_ORIGINS = [
    "http://localhost:8000",
    "http://127.0.0.1:8000",
    "http://localhost:5173",
    "http://127.0.0.1:5173",
    "https://localhost:5173",
    "https://*.ngrok-free.app",
]
