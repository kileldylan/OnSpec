import hmac
import logging
import secrets
from urllib.parse import urlencode

from django.contrib.auth import authenticate, get_user_model, login, logout
from django.db import IntegrityError, transaction
from django.http import HttpResponseRedirect
from django.middleware.csrf import get_token
from django.conf import settings
from django.views.decorators.csrf import csrf_protect
from django.views.decorators.csrf import ensure_csrf_cookie
from rest_framework import serializers, status
from rest_framework.decorators import api_view, permission_classes
from rest_framework.permissions import AllowAny, IsAuthenticated
from rest_framework.response import Response

from ACI_backend.ACIApp.models import GitHubAccount
from ACI_backend.integrations.github.accounts import (
    link_github_account_repositories,
)
from ACI_backend.integrations.github.oauth import GitHubOAuthError, exchange_code


User = get_user_model()
logger = logging.getLogger(__name__)


class RegistrationSerializer(serializers.Serializer):
    username = serializers.CharField(max_length=150)
    email = serializers.EmailField()
    password = serializers.CharField(write_only=True, min_length=8)
    password_confirm = serializers.CharField(write_only=True)

    def validate_username(self, value):
        if User.objects.filter(username__iexact=value).exists():
            raise serializers.ValidationError("A user with that username already exists.")
        return value

    def validate_email(self, value):
        if User.objects.filter(email__iexact=value).exists():
            raise serializers.ValidationError("A user with that email already exists.")
        return value

    def validate(self, attrs):
        if attrs["password"] != attrs.pop("password_confirm"):
            raise serializers.ValidationError({"password_confirm": "Passwords do not match."})
        user = User(username=attrs["username"], email=attrs["email"])
        from django.contrib.auth.password_validation import validate_password

        validate_password(attrs["password"], user=user)
        return attrs

    def create(self, validated_data):
        return User.objects.create_user(**validated_data)


class LoginSerializer(serializers.Serializer):
    username = serializers.CharField()
    password = serializers.CharField(write_only=True, trim_whitespace=False)


def user_payload(user):
    github_account = getattr(user, "github_account", None)
    return {
        "id": user.id,
        "username": user.username,
        "email": user.email,
        "first_name": user.first_name,
        "last_name": user.last_name,
        "github_login": github_account.github_login if github_account else None,
    }


@api_view(["GET"])
@permission_classes([AllowAny])
@ensure_csrf_cookie
def csrf_token(request):
    return Response({"csrfToken": get_token(request)})


@api_view(["POST"])
@permission_classes([AllowAny])
@csrf_protect
def register(request):
    serializer = RegistrationSerializer(data=request.data)
    serializer.is_valid(raise_exception=True)
    user = serializer.save()
    login(request, user)
    return Response({"user": user_payload(user)}, status=status.HTTP_201_CREATED)


@api_view(["POST"])
@permission_classes([AllowAny])
@csrf_protect
def login_view(request):
    serializer = LoginSerializer(data=request.data)
    serializer.is_valid(raise_exception=True)
    identifier = serializer.validated_data["username"]
    password = serializer.validated_data["password"]
    username = identifier
    if "@" in identifier:
        username = User.objects.filter(email__iexact=identifier).values_list(
            "username", flat=True
        ).first()
    user = authenticate(request, username=username, password=password)
    if user is None:
        return Response(
            {"detail": "Invalid username/email or password."},
            status=status.HTTP_400_BAD_REQUEST,
        )
    login(request, user)
    return Response({"user": user_payload(user)})


@api_view(["POST"])
@permission_classes([IsAuthenticated])
def logout_view(request):
    logout(request)
    return Response(status=status.HTTP_204_NO_CONTENT)


@api_view(["GET"])
@permission_classes([AllowAny])
def current_user(request):
    if not request.user.is_authenticated:
        return Response({"user": None})
    return Response({"user": user_payload(request.user)})


@api_view(["GET"])
@permission_classes([IsAuthenticated])
def github_oauth_connect(request):
    return _github_oauth_authorization_response(request, mode="link")


@api_view(["GET"])
@permission_classes([AllowAny])
def github_oauth_login(request):
    return _github_oauth_authorization_response(request, mode="login")


def _github_oauth_authorization_response(request, *, mode):
    if (
        not settings.GITHUB_OAUTH_CLIENT_ID
        or not settings.GITHUB_OAUTH_CLIENT_SECRET
    ):
        return Response(
            {"detail": "GitHub account connection is not configured."},
            status=status.HTTP_503_SERVICE_UNAVAILABLE,
        )

    state = secrets.token_urlsafe(32)
    request.session["github_oauth_state"] = state
    request.session["github_oauth_mode"] = mode
    query = urlencode(
        {
            "client_id": settings.GITHUB_OAUTH_CLIENT_ID,
            "redirect_uri": settings.GITHUB_OAUTH_REDIRECT_URI,
            "scope": "read:user",
            "state": state,
        }
    )
    return Response(
        {"authorization_url": f"https://github.com/login/oauth/authorize?{query}"}
    )


@api_view(["GET"])
@permission_classes([AllowAny])
def github_oauth_callback(request):
    state = request.query_params.get("state", "")
    expected_state = request.session.pop("github_oauth_state", "")
    mode = request.session.pop("github_oauth_mode", "link")
    if (
        not expected_state
        or not state
        or not hmac.compare_digest(state, expected_state)
    ):
        return _github_oauth_redirect("invalid_state", mode=mode)

    if request.query_params.get("error"):
        return _github_oauth_redirect("cancelled", mode=mode)

    code = request.query_params.get("code")
    if not code:
        return _github_oauth_redirect("failed", mode=mode)

    try:
        github_user = exchange_code(code)
    except GitHubOAuthError:
        logger.exception("GitHub OAuth exchange failed.")
        return _github_oauth_redirect("failed", mode=mode)

    try:
        with transaction.atomic():
            account = GitHubAccount.objects.select_related("user").filter(
                github_id=github_user["id"],
            ).first()
            if mode == "link":
                if not request.user.is_authenticated:
                    return _github_oauth_redirect("login_required", mode=mode)
                account_for_user = GitHubAccount.objects.filter(
                    user=request.user,
                ).first()
                if (
                    account_for_user
                    and account_for_user.github_id != github_user["id"]
                ):
                    return _github_oauth_redirect(
                        "account_mismatch",
                        mode=mode,
                    )
                if account and account.user_id != request.user.id:
                    return _github_oauth_redirect(
                        "already_linked",
                        mode=mode,
                    )
                user = request.user
                if account is None:
                    account = GitHubAccount(user=user)
            elif mode == "login":
                if account is None:
                    username = f"github-{github_user['id']}"
                    user = User.objects.create_user(
                        username=username,
                        email="",
                        password=None,
                    )
                    account = GitHubAccount(
                        user=user,
                        github_id=github_user["id"],
                        github_login=github_user["login"],
                    )
                else:
                    user = account.user
            else:
                return _github_oauth_redirect("invalid_state", mode=mode)

            account.github_id = github_user["id"]
            account.github_login = github_user["login"]
            account.save()
            link_github_account_repositories(account)
    except IntegrityError:
        logger.exception("GitHub account could not be linked to the ACI user.")
        return _github_oauth_redirect("already_linked", mode=mode)

    if mode == "login":
        login(request, user)
        return HttpResponseRedirect(f"{settings.FRONTEND_URL}/")
    return _github_oauth_redirect("connected", mode=mode)


def _github_oauth_redirect(result, *, mode="link"):
    if mode == "login":
        return HttpResponseRedirect(
            f"{settings.FRONTEND_URL}/login?github={result}"
        )
    return HttpResponseRedirect(f"{settings.FRONTEND_URL}/?github={result}")