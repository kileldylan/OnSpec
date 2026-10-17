import pytest
from django.contrib.auth import get_user_model
from django.urls import reverse
from rest_framework.test import APIClient


@pytest.mark.django_db
def test_register_logs_user_in():
    response = APIClient().post(
        reverse("auth-register"),
        {
            "username": "new-user",
            "email": "new@example.com",
            "password": "strong-password-123",
            "password_confirm": "strong-password-123",
        },
        format="json",
    )

    assert response.status_code == 201
    assert response.json()["user"]["username"] == "new-user"
    assert response.wsgi_request.user.is_authenticated


@pytest.mark.django_db
def test_login_accepts_email_and_me_returns_user():
    user = get_user_model().objects.create_user(
        username="login-user",
        email="login@example.com",
        password="strong-password-123",
    )
    client = APIClient()

    response = client.post(
        reverse("auth-login"),
        {"username": user.email, "password": "strong-password-123"},
        format="json",
    )

    assert response.status_code == 200
    assert client.get(reverse("auth-me")).json()["user"]["id"] == user.id


@pytest.mark.django_db
def test_login_rejects_invalid_credentials():
    get_user_model().objects.create_user(
        username="existing-user",
        password="strong-password-123",
    )

    response = APIClient().post(
        reverse("auth-login"),
        {"username": "existing-user", "password": "wrong-password"},
        format="json",
    )

    assert response.status_code == 400


@pytest.mark.django_db
def test_current_user_returns_null_for_anonymous_session():
    response = APIClient().get(reverse("auth-me"))

    assert response.status_code == 200
    assert response.json() == {"user": None}


@pytest.mark.django_db
def test_login_rejects_missing_fields():
    response = APIClient().post(
        reverse("auth-login"),
        {"password": "strong-password-123"},
        format="json",
    )

    assert response.status_code == 400
    assert "username" in response.json()


@pytest.mark.django_db
def test_login_requires_csrf_token():
    client = APIClient(enforce_csrf_checks=True)
    response = client.post(
        reverse("auth-login"),
        {"username": "missing-user", "password": "wrong-password"},
        format="json",
    )
    assert response.status_code == 403

    csrf_response = client.get(reverse("auth-csrf"))
    csrf_token = csrf_response.cookies["csrftoken"].value
    response = client.post(
        reverse("auth-login"),
        {"username": "missing-user", "password": "wrong-password"},
        format="json",
        HTTP_X_CSRFTOKEN=csrf_token,
    )

    assert response.status_code == 400


@pytest.mark.django_db
def test_register_requires_csrf_token():
    client = APIClient(enforce_csrf_checks=True)
    data = {
        "username": "csrf-user",
        "email": "csrf@example.com",
        "password": "strong-password-123",
        "password_confirm": "strong-password-123",
    }
    response = client.post(reverse("auth-register"), data, format="json")

    assert response.status_code == 403

    csrf_response = client.get(reverse("auth-csrf"))
    csrf_token = csrf_response.cookies["csrftoken"].value
    response = client.post(
        reverse("auth-register"),
        data,
        format="json",
        HTTP_X_CSRFTOKEN=csrf_token,
    )

    assert response.status_code == 201
    assert response.json()["user"]["username"] == "csrf-user"
