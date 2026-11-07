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
GITHUB_ACCESS_TOKEN = env("GITHUB_ACCESS_TOKEN", default="")
GITHUB_APP_ID = env("GITHUB_APP_ID", default="")
GITHUB_APP_PRIVATE_KEY = env("GITHUB_APP_PRIVATE_KEY", default="")
GITHUB_API_TIMEOUT = env.int("GITHUB_API_TIMEOUT", default=15)
GITHUB_WEBHOOK_MAX_BYTES = env.int(
    "GITHUB_WEBHOOK_MAX_BYTES",
    default=25 * 1024 * 1024,
)
GITHUB_CACHE_MAX_BYTES = env.int(
    "GITHUB_CACHE_MAX_BYTES",
    default=1 * 1024 * 1024,
)
REDIS_URL = env("REDIS_URL", default="")
GITHUB_OAUTH_CLIENT_ID = env("GITHUB_OAUTH_CLIENT_ID", default="")
GITHUB_OAUTH_CLIENT_SECRET = env("GITHUB_OAUTH_CLIENT_SECRET", default="")
GITHUB_OAUTH_REDIRECT_URI = env(
    "GITHUB_OAUTH_REDIRECT_URI",
    default="https://api.deelan.co.ke/api/auth/github/callback/",
)
FRONTEND_URL = env(
    "FRONTEND_URL",
    default="https://on-spec.vercel.app",
).rstrip("/")
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

# Safely get hosts from environment, defaulting to an empty list
ALLOWED_HOSTS = env.list("ALLOWED_HOSTS", default=[])

# Always include these, no matter what the environment variable says
REQUIRED_HOSTS = [
    "onspec.onrender.com",
    "deelan.co.ke",
    "www.deelan.co.ke",
    "api.deelan.co.ke",
    "app.deelan.co.ke",
    "requora.deelan.co.ke",
]
if DEBUG:
    REQUIRED_HOSTS.extend(["localhost", "127.0.0.1"])

for host in REQUIRED_HOSTS:
    if host not in ALLOWED_HOSTS:
        ALLOWED_HOSTS.append(host)

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
    "corsheaders",

]

# =============================================================================
# MIDDLEWARE
# =============================================================================

MIDDLEWARE = [
    "corsheaders.middleware.CorsMiddleware",
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

DATABASE_URL = env("DATABASE_URL", default="")
if DATABASE_URL:
    DATABASES = {"default": env.db_url("DATABASE_URL")}
else:
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

CORS_ALLOWED_ORIGINS = [
    "https://on-spec.vercel.app",
    "https://deelan.co.ke",
    "https://www.deelan.co.ke",
    "https://app.deelan.co.ke",
    "https://requora.deelan.co.ke",
]
if DEBUG:
    CORS_ALLOWED_ORIGINS.extend(
        ["http://localhost:5173", "http://127.0.0.1:5173"]
    )
CORS_ALLOWED_ORIGINS = env.list(
    "CORS_ALLOWED_ORIGINS",
    default=CORS_ALLOWED_ORIGINS,
)

# Allow cookies/sessions/CSRF tokens to be passed
CORS_ALLOW_CREDENTIALS = True

CSRF_TRUSTED_ORIGINS = [
    "https://on-spec.vercel.app",
    "https://onspec.onrender.com",
    "https://deelan.co.ke",
    "https://www.deelan.co.ke",
    "https://api.deelan.co.ke",
    "https://app.deelan.co.ke",
    "https://requora.deelan.co.ke",
]
if DEBUG:
    CSRF_TRUSTED_ORIGINS.append("http://localhost:5173")
CSRF_TRUSTED_ORIGINS = env.list(
    "CSRF_TRUSTED_ORIGINS",
    default=CSRF_TRUSTED_ORIGINS,
)

# Trust Render's proxy to tell Django the request is HTTPS
SECURE_PROXY_SSL_HEADER = ('HTTP_X_FORWARDED_PROTO', 'https')

# Ensure CSRF cookies are sent over HTTPS in production
CSRF_COOKIE_SECURE = True
SESSION_COOKIE_SECURE = True
CSRF_COOKIE_HTTPONLY = True
SESSION_COOKIE_HTTPONLY = True

# If your frontend and backend are on different domains (Vercel vs Render), 
# you MUST use SameSite=None for cross-site cookies.
CSRF_COOKIE_SAMESITE = 'None'
SESSION_COOKIE_SAMESITE = 'None'

# Redis is shared by the Render web and worker processes. Local development
# remains usable without Redis, but production must set REDIS_URL for
# distributed API throttling and GitHub token/read caching.
if REDIS_URL:
    CACHES = {
        "default": {
            "BACKEND": "django_redis.cache.RedisCache",
            "LOCATION": REDIS_URL,
            "OPTIONS": {
                "CLIENT_CLASS": "django_redis.client.DefaultClient",
                "SERIALIZER": "django_redis.serializers.json.JSONSerializer",
                "SOCKET_CONNECT_TIMEOUT": 5,
                "SOCKET_TIMEOUT": 5,
                "CONNECTION_POOL_KWARGS": {"max_connections": 100},
            },
            "KEY_PREFIX": "onspec",
        },
    }
else:
    CACHES = {
        "default": {
            "BACKEND": "django.core.cache.backends.locmem.LocMemCache",
            "LOCATION": "onspec-local",
        },
    }

SECURE_SSL_REDIRECT = env.bool(
    "SECURE_SSL_REDIRECT",
    default=not DEBUG,
)
SECURE_HSTS_SECONDS = env.int(
    "SECURE_HSTS_SECONDS",
    default=31_536_000 if not DEBUG else 0,
)
SECURE_HSTS_INCLUDE_SUBDOMAINS = env.bool(
    "SECURE_HSTS_INCLUDE_SUBDOMAINS",
    default=False,
)
SECURE_HSTS_PRELOAD = env.bool("SECURE_HSTS_PRELOAD", default=False)
SECURE_CONTENT_TYPE_NOSNIFF = True
SECURE_REFERRER_POLICY = "same-origin"

DATA_UPLOAD_MAX_MEMORY_SIZE = env.int(
    "DATA_UPLOAD_MAX_MEMORY_SIZE",
    default=25 * 1024 * 1024,
)

REST_FRAMEWORK.update(
    {
        "DEFAULT_THROTTLE_CLASSES": [
            "rest_framework.throttling.AnonRateThrottle",
            "rest_framework.throttling.UserRateThrottle",
        ],
        "DEFAULT_THROTTLE_RATES": {
            "anon": "60/minute",
            "user": "600/hour",
            "auth_login_ip": "10/minute",
            "auth_login_account": "10/minute",
            "auth_registration": "5/hour",
            "github_oauth": "20/minute",
        },
    }
)