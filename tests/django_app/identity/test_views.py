import uuid
import logging
import pytest
from django.core import mail
from django.test import override_settings
from django.urls import reverse
from rest_framework.test import APIClient

from domain.identity.entities import User, UserRole
from domain.identity.value_objects import Email, PasswordHash, PlainPassword
from infrastructure.repos.django_user_repository import DjangoUserRepository
from infrastructure.adapters.password_hasher import DjangoPasswordHasher
from django_app.identity.models import User as DjangoUser

pytestmark = pytest.mark.django_db(transaction=True)

GENERIC_FORGOT_PASSWORD_DETAIL = "If an account exists for that email, password reset instructions have been sent."


class TestIdentityViews:
    @pytest.fixture(autouse=True)
    def setup(self):
        self.repo = DjangoUserRepository()
        self.hasher = DjangoPasswordHasher()
        self.client = APIClient()

    def test_register_success(self):
        url = reverse("register")
        data = {
            "email": "new@example.com",
            "password": "StrongPass1",
            "first_name": "Test",
            "last_name": "User",
            "role": "planner",
        }
        response = self.client.post(url, data, format="json")
        assert response.status_code == 201
        assert response.data["email"] == "new@example.com"

        user = self.repo.get_by_email(Email("new@example.com"))
        assert user is not None

    def test_register_duplicate_email(self):
        plain = PlainPassword("StrongPass1")
        hashed = self.hasher.hash(plain)
        user = User(
            id=uuid.uuid4(),
            email=Email("exists@example.com"),
            password_hash=PasswordHash(hashed),
            first_name="A",
            last_name="B",
            role=UserRole.PLANNER,
        )
        self.repo.save(user)

        url = reverse("register")
        data = {
            "email": "exists@example.com",
            "password": "StrongPass1",
            "first_name": "Test",
            "last_name": "User",
            "role": "planner",
        }
        response = self.client.post(url, data, format="json")
        assert response.status_code == 400
        assert "already exists" in str(response.data["error"])

    def test_register_then_login_success(self):
        register_url = reverse("register")
        login_url = reverse("login")

        register_response = self.client.post(
            register_url,
            {
                "email": "fresh@example.com",
                "password": "StrongPass1",
                "first_name": "Fresh",
                "last_name": "User",
                "role": "planner",
            },
            format="json",
        )
        assert register_response.status_code == 201

        login_response = self.client.post(
            login_url,
            {
                "email": "fresh@example.com",
                "password": "StrongPass1",
            },
            format="json",
        )
        assert login_response.status_code == 200
        assert "access_token" in login_response.data
        assert "refresh_token" not in login_response.data
        assert "user" in login_response.data
        assert login_response.data["user"]["display_name"] == "Fresh User"
        assert login_response.data["user"]["requires_password_setup"] is False
        assert "refresh_token" in login_response.cookies

    def test_login_success(self):
        plain = PlainPassword("StrongPass1")
        hashed = self.hasher.hash(plain)
        user = User(
            id=uuid.uuid4(),
            email=Email("login@example.com"),
            password_hash=PasswordHash(hashed),
            first_name="L",
            last_name="User",
            role=UserRole.PLANNER,
            is_active=True,
        )
        self.repo.save(user)

    def test_login_wrong_password(self):
        plain = PlainPassword("Correct1")
        hashed = self.hasher.hash(plain)

        # Sanity check: hasher works as expected
        assert self.hasher.verify(PlainPassword("Correct1"), PasswordHash(hashed)) is True
        assert self.hasher.verify(PlainPassword("WrongPass1"), PasswordHash(hashed)) is False

        user = User(
            id=uuid.uuid4(),
            email=Email("wrong-login@example.com"),
            password_hash=PasswordHash(hashed),
            first_name="W",
            last_name="User",
            role=UserRole.PLANNER,
        )
        self.repo.save(user)

        url = reverse("login")
        data = {"email": "wrong-login@example.com", "password": "WrongPass1"}
        response = self.client.post(url, data, format="json")
        assert response.status_code == 401
        assert "error" in response.data

    def test_profile_endpoint_returns_authenticated_user(self):
        user = DjangoUser.objects.create_user(
            email="profile@example.com",
            password="StrongPass1",
            first_name="Profile",
            last_name="User",
            role="planner",
        )
        self.client.force_authenticate(user=user)

        response = self.client.get(reverse("profile"))
        assert response.status_code == 200
        assert response.data["email"] == "profile@example.com"
        assert response.data["role"] == "planner"
        assert response.data["requires_password_setup"] is False

    def test_profile_update_preserves_password_setup_state(self):
        user = DjangoUser.objects.create_user(
            email="vendor-profile@example.com",
            password="StrongPass1",
            first_name="Vendor",
            last_name="User",
            role="vendor",
        )
        self.client.force_authenticate(user=user)

        response = self.client.patch(
            reverse("profile"),
            {"first_name": "Updated", "last_name": "Vendor"},
            format="json",
        )

        assert response.status_code == 200
        assert response.data["first_name"] == "Updated"
        assert response.data["requires_password_setup"] is False
        assert response.data["has_password"] is True

    def test_refresh_token_returns_access_token(self):
        user = DjangoUser.objects.create_user(
            email="refresh@example.com",
            password="StrongPass1",
            first_name="Refresh",
            last_name="User",
            role="planner",
        )
        self.client.force_authenticate(user=user)
        login_response = self.client.post(
            reverse("login"),
            {"email": "refresh@example.com", "password": "StrongPass1"},
            format="json",
        )
        refresh_token = login_response.cookies["refresh_token"].value

        self.client.credentials()
        response = self.client.post(reverse("token-refresh"), {"refresh": refresh_token}, format="json")
        assert response.status_code == 200
        assert "access" in response.data
        assert "user" in response.data
        assert "refresh_token" in response.cookies

    def test_refresh_token_can_use_cookie(self):
        user = DjangoUser.objects.create_user(
            email="cookie-refresh@example.com",
            password="StrongPass1",
            first_name="Cookie",
            last_name="Refresh",
            role="planner",
        )
        login_response = self.client.post(
            reverse("login"),
            {"email": "cookie-refresh@example.com", "password": "StrongPass1"},
            format="json",
        )
        refresh_token = login_response.cookies["refresh_token"].value

        self.client.cookies["refresh_token"] = refresh_token
        response = self.client.post(reverse("token-refresh"), format="json")
        assert response.status_code == 200
        assert "access" in response.data
        assert "user" in response.data

    def test_revoke_token_clears_cookies(self):
        user = DjangoUser.objects.create_user(
            email="revoke@example.com",
            password="StrongPass1",
            first_name="Revoke",
            last_name="User",
            role="planner",
        )
        login_response = self.client.post(
            reverse("login"),
            {"email": "revoke@example.com", "password": "StrongPass1"},
            format="json",
        )
        refresh_token = login_response.cookies["refresh_token"].value

        response = self.client.post(reverse("token-revoke"), {"refresh": refresh_token}, format="json")
        assert response.status_code == 200
        assert response.data["status"] == "revoked"
        assert "access_token" in response.cookies
        assert response.cookies["access_token"].value == ""
        assert response.cookies["access_token"]["max-age"] == 0
        assert "refresh_token" in response.cookies
        assert response.cookies["refresh_token"].value == ""
        assert response.cookies["refresh_token"]["max-age"] == 0

    @override_settings(
        EMAIL_BACKEND="django.core.mail.backends.locmem.EmailBackend",
        DEFAULT_FROM_EMAIL="no-reply@example.test",
        FRONTEND_URL="https://app.example.test",
    )
    def test_forgot_password_existing_active_user_sends_email(self):
        mail.outbox = []
        DjangoUser.objects.create_user(
            email="reset@example.com",
            password="StrongPass1",
            first_name="Reset",
            last_name="User",
            role="planner",
        )

        response = self.client.post(reverse("forgot-password"), {"email": "reset@example.com"}, format="json")

        assert response.status_code == 202
        assert response.data == {"detail": GENERIC_FORGOT_PASSWORD_DETAIL}
        assert len(mail.outbox) == 1
        message = mail.outbox[0]
        assert message.subject == "Reset your LinkaPro password"
        assert message.from_email == "no-reply@example.test"
        assert message.to == ["reset@example.com"]
        assert "LinkaPro password reset request" in message.body
        assert "https://app.example.test/auth/reset-password?token=" in message.body
        assert "This link expires in 1 hour." in message.body

    @override_settings(
        EMAIL_BACKEND="django.core.mail.backends.locmem.EmailBackend",
        DEFAULT_FROM_EMAIL="no-reply@example.test",
        FRONTEND_URL="https://app.example.test",
    )
    def test_forgot_password_nonexistent_email_returns_generic_without_email(self):
        mail.outbox = []

        response = self.client.post(reverse("forgot-password"), {"email": "missing@example.com"}, format="json")

        assert response.status_code == 202
        assert response.data == {"detail": GENERIC_FORGOT_PASSWORD_DETAIL}
        assert mail.outbox == []

    @override_settings(
        EMAIL_BACKEND="django.core.mail.backends.locmem.EmailBackend",
        DEFAULT_FROM_EMAIL="no-reply@example.test",
        FRONTEND_URL="https://app.example.test",
    )
    def test_forgot_password_inactive_user_returns_generic_without_email(self):
        mail.outbox = []
        DjangoUser.objects.create_user(
            email="inactive@example.com",
            password="StrongPass1",
            first_name="Inactive",
            last_name="User",
            role="planner",
            is_active=False,
        )

        response = self.client.post(reverse("forgot-password"), {"email": "inactive@example.com"}, format="json")

        assert response.status_code == 202
        assert response.data == {"detail": GENERIC_FORGOT_PASSWORD_DETAIL}
        assert mail.outbox == []

    @override_settings(
        EMAIL_BACKEND="django.core.mail.backends.locmem.EmailBackend",
        DEFAULT_FROM_EMAIL="no-reply@example.test",
        FRONTEND_URL="https://app.example.test",
    )
    def test_forgot_password_does_not_log_reset_token(self, caplog):
        mail.outbox = []
        DjangoUser.objects.create_user(
            email="nolog@example.com",
            password="StrongPass1",
            first_name="No",
            last_name="Log",
            role="planner",
        )
        caplog.set_level(logging.INFO, logger="django_app.identity.password_reset_email")

        response = self.client.post(reverse("forgot-password"), {"email": "nolog@example.com"}, format="json")

        assert response.status_code == 202
        reset_token = mail.outbox[0].body.split("token=", 1)[1].splitlines()[0]
        assert reset_token
        assert reset_token not in caplog.text
        assert "/auth/reset-password?token=" not in caplog.text
        assert "nolog@example.com" not in caplog.text

    @override_settings(
        EMAIL_BACKEND="django.core.mail.backends.locmem.EmailBackend",
        DEFAULT_FROM_EMAIL="no-reply@example.test",
        FRONTEND_URL="https://app.example.test",
    )
    def test_forgot_password_provider_failure_still_returns_generic(self, caplog, monkeypatch):
        mail.outbox = []
        DjangoUser.objects.create_user(
            email="fail@example.com",
            password="StrongPass1",
            first_name="Fail",
            last_name="User",
            role="planner",
        )

        def fail_send_mail(*args, **kwargs):
            raise RuntimeError("provider unavailable")

        monkeypatch.setattr("django_app.identity.password_reset_email.send_mail", fail_send_mail)
        caplog.set_level(logging.ERROR, logger="django_app.identity.password_reset_email")

        response = self.client.post(reverse("forgot-password"), {"email": "fail@example.com"}, format="json")

        assert response.status_code == 202
        assert response.data == {"detail": GENERIC_FORGOT_PASSWORD_DETAIL}
        assert mail.outbox == []
        assert "forgot_password_email_failed" in caplog.text
        assert "/auth/reset-password?token=" not in caplog.text
