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
from infrastructure.adapters.jwt_token_service import JWTTokenService
from django_app.identity.models import User as DjangoUser
from tasks.email_tasks import send_password_reset_email_task

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
    def test_forgot_password_existing_active_user_enqueues_email(self, monkeypatch):
        mail.outbox = []
        enqueued = {}
        DjangoUser.objects.create_user(
            email="reset@example.com",
            password="StrongPass1",
            first_name="Reset",
            last_name="User",
            role="planner",
        )

        def capture_delay(user_id, token):
            enqueued["user_id"] = user_id
            enqueued["token"] = token

        monkeypatch.setattr("tasks.email_tasks.send_password_reset_email_task.delay", capture_delay)

        response = self.client.post(reverse("forgot-password"), {"email": "reset@example.com"}, format="json")

        assert response.status_code == 202
        assert response.data == {"detail": GENERIC_FORGOT_PASSWORD_DETAIL}
        assert enqueued["user_id"]
        assert enqueued["token"]
        assert mail.outbox == []

    @override_settings(
        EMAIL_BACKEND="django.core.mail.backends.locmem.EmailBackend",
        DEFAULT_FROM_EMAIL="no-reply@example.test",
        FRONTEND_URL="https://app.example.test",
    )
    def test_forgot_password_nonexistent_email_returns_generic_without_enqueue(self, monkeypatch):
        mail.outbox = []
        enqueued = []
        monkeypatch.setattr("tasks.email_tasks.send_password_reset_email_task.delay", lambda *args: enqueued.append(args))

        response = self.client.post(reverse("forgot-password"), {"email": "missing@example.com"}, format="json")

        assert response.status_code == 202
        assert response.data == {"detail": GENERIC_FORGOT_PASSWORD_DETAIL}
        assert mail.outbox == []
        assert enqueued == []

    @override_settings(
        EMAIL_BACKEND="django.core.mail.backends.locmem.EmailBackend",
        DEFAULT_FROM_EMAIL="no-reply@example.test",
        FRONTEND_URL="https://app.example.test",
    )
    def test_forgot_password_inactive_user_returns_generic_without_enqueue(self, monkeypatch):
        mail.outbox = []
        enqueued = []
        monkeypatch.setattr("tasks.email_tasks.send_password_reset_email_task.delay", lambda *args: enqueued.append(args))
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
        assert enqueued == []

    @override_settings(
        EMAIL_BACKEND="django.core.mail.backends.locmem.EmailBackend",
        DEFAULT_FROM_EMAIL="no-reply@example.test",
        FRONTEND_URL="https://app.example.test",
    )
    def test_forgot_password_does_not_log_reset_token(self, caplog, monkeypatch):
        mail.outbox = []
        enqueued = {}
        DjangoUser.objects.create_user(
            email="nolog@example.com",
            password="StrongPass1",
            first_name="No",
            last_name="Log",
            role="planner",
        )

        def capture_delay(user_id, token):
            enqueued["user_id"] = user_id
            enqueued["token"] = token

        monkeypatch.setattr("tasks.email_tasks.send_password_reset_email_task.delay", capture_delay)
        caplog.set_level(logging.INFO, logger="django_app.identity.password_reset_email")

        response = self.client.post(reverse("forgot-password"), {"email": "nolog@example.com"}, format="json")

        assert response.status_code == 202
        reset_token = enqueued["token"]
        assert reset_token
        assert reset_token not in caplog.text
        assert "/auth/reset-password?token=" not in caplog.text
        assert "nolog@example.com" not in caplog.text

    @override_settings(
        EMAIL_BACKEND="django.core.mail.backends.locmem.EmailBackend",
        DEFAULT_FROM_EMAIL="no-reply@example.test",
        FRONTEND_URL="https://app.example.test",
    )
    def test_forgot_password_dispatch_failure_still_returns_generic(self, caplog, monkeypatch):
        mail.outbox = []
        DjangoUser.objects.create_user(
            email="fail@example.com",
            password="StrongPass1",
            first_name="Fail",
            last_name="User",
            role="planner",
        )

        def fail_delay(*args, **kwargs):
            raise RuntimeError("redis unavailable")

        monkeypatch.setattr("tasks.email_tasks.send_password_reset_email_task.delay", fail_delay)
        caplog.set_level(logging.ERROR, logger="django_app.identity.password_reset_email")

        response = self.client.post(reverse("forgot-password"), {"email": "fail@example.com"}, format="json")

        assert response.status_code == 202
        assert response.data == {"detail": GENERIC_FORGOT_PASSWORD_DETAIL}
        assert mail.outbox == []
        assert "forgot_password_email_dispatch_deferred" in caplog.text
        assert "/auth/reset-password?token=" not in caplog.text

    @override_settings(
        EMAIL_BACKEND="django.core.mail.backends.locmem.EmailBackend",
        DEFAULT_FROM_EMAIL="no-reply@example.test",
        FRONTEND_URL="https://app.example.test",
    )
    def test_password_reset_email_task_sends_email_for_active_user(self):
        mail.outbox = []
        user = DjangoUser.objects.create_user(
            email="task-reset@example.com",
            password="StrongPass1",
            first_name="Task",
            last_name="Reset",
            role="planner",
        )
        token = JWTTokenService().create_password_reset_token(str(user.id))

        result = send_password_reset_email_task.apply(args=[str(user.id), token]).get()

        assert result is True
        assert len(mail.outbox) == 1
        message = mail.outbox[0]
        assert message.subject == "Reset your LinkaPro password"
        assert message.from_email == "no-reply@example.test"
        assert message.to == ["task-reset@example.com"]
        assert "LinkaPro password reset request" in message.body
        assert f"https://app.example.test/auth/reset-password?token={token}" in message.body
        assert "This link expires in 1 hour." in message.body

    @override_settings(
        EMAIL_BACKEND="django.core.mail.backends.locmem.EmailBackend",
        DEFAULT_FROM_EMAIL="no-reply@example.test",
        FRONTEND_URL="https://app.example.test",
    )
    def test_password_reset_email_task_skips_missing_or_inactive_user(self):
        mail.outbox = []
        inactive_user = DjangoUser.objects.create_user(
            email="inactive-task-reset@example.com",
            password="StrongPass1",
            first_name="Inactive",
            last_name="Task",
            role="planner",
            is_active=False,
        )

        missing_result = send_password_reset_email_task.apply(args=[str(uuid.uuid4()), "token"]).get()
        inactive_result = send_password_reset_email_task.apply(args=[str(inactive_user.id), "token"]).get()

        assert missing_result is False
        assert inactive_result is False
        assert mail.outbox == []

    @override_settings(
        EMAIL_BACKEND="django.core.mail.backends.locmem.EmailBackend",
        DEFAULT_FROM_EMAIL="no-reply@example.test",
        FRONTEND_URL="https://app.example.test",
    )
    def test_password_reset_email_task_does_not_log_token(self, caplog):
        mail.outbox = []
        user = DjangoUser.objects.create_user(
            email="task-nolog@example.com",
            password="StrongPass1",
            first_name="Task",
            last_name="NoLog",
            role="planner",
        )
        token = JWTTokenService().create_password_reset_token(str(user.id))
        caplog.set_level(logging.INFO, logger="django_app.identity.password_reset_email")

        result = send_password_reset_email_task.apply(args=[str(user.id), token]).get()

        assert result is True
        assert token not in caplog.text
        assert "/auth/reset-password?token=" not in caplog.text

    def test_reset_password_missing_token_returns_controlled_field_error(self):
        response = self.client.post(
            reverse("reset-password"),
            {"new_password": "ValidPass1!"},
            format="json",
        )

        assert response.status_code == 400
        assert response.data["code"] == "password_reset_invalid"
        assert response.data["message"] == "Please fix the highlighted fields."
        assert "token" in response.data["field_errors"]

    def test_reset_password_weak_password_returns_new_password_field_error(self):
        token = JWTTokenService().create_password_reset_token(str(uuid.uuid4()))

        response = self.client.post(
            reverse("reset-password"),
            {"token": token, "new_password": "weak"},
            format="json",
        )

        assert response.status_code == 400
        assert response.data["code"] == "password_reset_invalid"
        assert response.data["message"] == "Please fix the highlighted fields."
        assert "new_password" in response.data["field_errors"]

    def test_reset_password_invalid_token_returns_token_invalid_response(self):
        response = self.client.post(
            reverse("reset-password"),
            {"token": "not-a-valid-token", "new_password": "ValidPass1!"},
            format="json",
        )

        assert response.status_code == 400
        assert response.data == {
            "code": "password_reset_token_invalid",
            "message": "This reset link has expired or is invalid.",
            "field_errors": {"token": ["Invalid or expired reset token."]},
        }

    def test_reset_password_missing_user_returns_same_token_invalid_response(self):
        token = JWTTokenService().create_password_reset_token(str(uuid.uuid4()))

        response = self.client.post(
            reverse("reset-password"),
            {"token": token, "new_password": "ValidPass1!"},
            format="json",
        )

        assert response.status_code == 400
        assert response.data == {
            "code": "password_reset_token_invalid",
            "message": "This reset link has expired or is invalid.",
            "field_errors": {"token": ["Invalid or expired reset token."]},
        }

    def test_reset_password_inactive_user_returns_same_token_invalid_response(self):
        user = DjangoUser.objects.create_user(
            email="inactive-reset@example.com",
            password="StrongPass1!",
            first_name="Inactive",
            last_name="Reset",
            role="planner",
            is_active=False,
        )
        token = JWTTokenService().create_password_reset_token(str(user.id))

        response = self.client.post(
            reverse("reset-password"),
            {"token": token, "new_password": "ValidPass1!"},
            format="json",
        )

        assert response.status_code == 400
        assert response.data == {
            "code": "password_reset_token_invalid",
            "message": "This reset link has expired or is invalid.",
            "field_errors": {"token": ["Invalid or expired reset token."]},
        }

    def test_reset_password_valid_token_resets_password_successfully(self):
        user = DjangoUser.objects.create_user(
            email="valid-reset@example.com",
            password="OldPass1!",
            first_name="Valid",
            last_name="Reset",
            role="planner",
        )
        token = JWTTokenService().create_password_reset_token(str(user.id))

        response = self.client.post(
            reverse("reset-password"),
            {"token": token, "new_password": "NewValidPass1!"},
            format="json",
        )

        user.refresh_from_db()
        assert response.status_code == 200
        assert response.data == {
            "status": "password_reset",
            "message": "Password updated successfully.",
        }
        assert user.check_password("NewValidPass1!") is True

    def test_reset_password_token_errors_do_not_expose_account_existence(self):
        inactive_user = DjangoUser.objects.create_user(
            email="hidden-reset@example.com",
            password="StrongPass1!",
            first_name="Hidden",
            last_name="Reset",
            role="planner",
            is_active=False,
        )
        missing_user_token = JWTTokenService().create_password_reset_token(str(uuid.uuid4()))
        inactive_user_token = JWTTokenService().create_password_reset_token(str(inactive_user.id))

        missing_response = self.client.post(
            reverse("reset-password"),
            {"token": missing_user_token, "new_password": "ValidPass1!"},
            format="json",
        )
        inactive_response = self.client.post(
            reverse("reset-password"),
            {"token": inactive_user_token, "new_password": "ValidPass1!"},
            format="json",
        )

        assert missing_response.status_code == 400
        assert inactive_response.status_code == 400
        assert missing_response.data == inactive_response.data
