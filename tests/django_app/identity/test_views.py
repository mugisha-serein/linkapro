import uuid
import logging
import pytest
from datetime import timedelta
from django.core import mail
from django.core.cache import cache
from django.test import override_settings
from django.urls import reverse
from django.utils import timezone
from rest_framework.test import APIClient

from domain.identity.entities import User, UserRole
from domain.identity.value_objects import Email, PasswordHash, PlainPassword
from infrastructure.repos.django_user_repository import DjangoUserRepository
from infrastructure.adapters.password_hasher import DjangoPasswordHasher
from infrastructure.adapters.jwt_token_service import JWTTokenService, password_reset_token_hash
from django_app.identity.models import PasswordResetEmailDelivery, PasswordResetToken, User as DjangoUser
from django_app.identity.password_reset_email import send_password_reset_email
from django_app.identity.throttles import rate_limit_hash
from tasks.email_tasks import send_password_reset_email_task

pytestmark = pytest.mark.django_db(transaction=True)

GENERIC_FORGOT_PASSWORD_DETAIL = "If an account exists for that email, password reset instructions have been sent."
FORGOT_PASSWORD_SUCCESS_RESPONSE = {
    "success": True,
    "code": "password_reset_email_queued",
    "message": GENERIC_FORGOT_PASSWORD_DETAIL,
    "data": {},
    "detail": GENERIC_FORGOT_PASSWORD_DETAIL,
}
PASSWORD_RESET_TOKEN_INVALID_RESPONSE = {
    "success": False,
    "code": "password_reset_token_invalid",
    "message": "This reset link has expired or is invalid.",
    "field_errors": {"token": ["Invalid or expired reset token."]},
}


def _auth_throttle_rates(**overrides):
    rates = {
        "login_ip": "100/min",
        "login_email": "100/min",
        "login_user": "100/hour",
        "register_ip": "100/hour",
        "register_email_domain": "100/hour",
        "two_factor_ip": "100/min",
        "two_factor_temp_token": "100/min",
    }
    rates.update(overrides)
    return {"DEFAULT_THROTTLE_RATES": rates}


def _create_delivery(user: DjangoUser, status=PasswordResetEmailDelivery.Status.QUEUED):
    return PasswordResetEmailDelivery.objects.create(
        user=user,
        email_hash="a" * 64,
        email_domain=user.email.rsplit("@", 1)[1],
        status=status,
        provider="locmem",
    )


def _issue_reset_token(user: DjangoUser) -> str:
    return JWTTokenService().issue_password_reset_token(user)


class TestIdentityViews:
    @pytest.fixture(autouse=True)
    def setup(self, monkeypatch):
        class InMemoryTokenBlacklist:
            blacklisted = set()
            blacklisted_families = set()

            def is_blacklisted(self, jti):
                return jti in self.blacklisted

            def blacklist(self, jti, ttl):
                self.blacklisted.add(jti)

            def is_family_blacklisted(self, family_id):
                return family_id in self.blacklisted_families

            def blacklist_family(self, family_id):
                self.blacklisted_families.add(family_id)

        monkeypatch.setattr("django_app.identity.services.RedisTokenBlacklist", InMemoryTokenBlacklist)
        cache.clear()
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
        assert response.data["success"] is True
        assert response.data["code"] == "registration_completed"
        assert response.data["data"]["user"]["email"] == "new@example.com"

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
        assert response.data["success"] is False
        assert response.data["code"] == "registration_validation_failed"
        assert "email" in response.data["field_errors"]

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
        assert login_response.data["success"] is True
        assert login_response.data["code"] == "login_completed"
        assert "access" in login_response.data["data"]
        assert "refresh_token" not in login_response.data
        assert "user" in login_response.data["data"]
        assert login_response.data["data"]["user"]["display_name"] == "Fresh User"
        assert login_response.data["data"]["user"]["requires_password_setup"] is False
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
        assert response.data["success"] is False
        assert response.data["code"] == "invalid_credentials"
        assert "error" not in response.data

    @override_settings(REST_FRAMEWORK=_auth_throttle_rates(login_ip="2/min"))
    def test_login_ip_throttle_blocks_after_configured_limit(self):
        for index in range(2):
            response = self.client.post(
                reverse("login"),
                {"email": f"ip-throttle-{index}@example.com", "password": "WrongPass1"},
                format="json",
                REMOTE_ADDR="203.0.113.10",
            )
            assert response.status_code == 401

        response = self.client.post(
            reverse("login"),
            {"email": "ip-throttle-final@example.com", "password": "WrongPass1"},
            format="json",
            REMOTE_ADDR="203.0.113.10",
        )

        assert response.status_code == 429
        assert response.data["success"] is False
        assert response.data["code"] == "login_rate_limited"
        assert response.data["message"] == "Too many sign-in attempts. Please try again later."
        assert response.data["field_errors"] == {}

    @override_settings(REST_FRAMEWORK=_auth_throttle_rates(login_email="2/min"))
    def test_login_email_throttle_blocks_repeated_same_email(self):
        for index in range(2):
            response = self.client.post(
                reverse("login"),
                {"email": "email-throttle@example.com", "password": "WrongPass1"},
                format="json",
                REMOTE_ADDR=f"203.0.113.{index + 20}",
            )
            assert response.status_code == 401

        response = self.client.post(
            reverse("login"),
            {"email": "email-throttle@example.com", "password": "WrongPass1"},
            format="json",
            REMOTE_ADDR="203.0.113.30",
        )

        assert response.status_code == 429
        assert response.data["code"] == "login_rate_limited"

    @override_settings(REST_FRAMEWORK=_auth_throttle_rates(login_user="2/hour"))
    def test_login_user_hour_throttle_blocks_repeated_same_user_identifier(self):
        for index in range(2):
            response = self.client.post(
                reverse("login"),
                {"email": "user-throttle@example.com", "password": "WrongPass1"},
                format="json",
                REMOTE_ADDR=f"203.0.113.{index + 40}",
            )
            assert response.status_code == 401

        response = self.client.post(
            reverse("login"),
            {"email": "user-throttle@example.com", "password": "WrongPass1"},
            format="json",
            REMOTE_ADDR="203.0.113.50",
        )

        assert response.status_code == 429
        assert response.data["code"] == "login_rate_limited"

    @override_settings(LOGIN_FAILURE_LOCKOUT_THRESHOLD=2, LOGIN_FAILURE_LOCKOUT_SECONDS=900)
    def test_failed_login_increments_progressive_counter_and_locks_out(self):
        for _ in range(2):
            response = self.client.post(
                reverse("login"),
                {"email": "progressive@example.com", "password": "WrongPass1"},
                format="json",
            )
            assert response.status_code == 401

        response = self.client.post(
            reverse("login"),
            {"email": "progressive@example.com", "password": "WrongPass1"},
            format="json",
        )

        assert response.status_code == 429
        assert response.data["code"] == "login_rate_limited"

    @override_settings(LOGIN_FAILURE_LOCKOUT_THRESHOLD=8, LOGIN_FAILURE_LOCKOUT_SECONDS=900)
    def test_successful_login_clears_progressive_failure_counter(self):
        user = DjangoUser.objects.create_user(
            email="clear-failure@example.com",
            password="StrongPass1",
            first_name="Clear",
            last_name="Failure",
            role="planner",
        )
        self.client.post(
            reverse("login"),
            {"email": "clear-failure@example.com", "password": "WrongPass1"},
            format="json",
        )

        email_hash = rate_limit_hash("clear-failure@example.com")
        assert cache.get(f"login_fail:{email_hash}") == 1

        response = self.client.post(
            reverse("login"),
            {"email": "clear-failure@example.com", "password": "StrongPass1"},
            format="json",
        )

        assert response.status_code == 200
        assert response.data["code"] == "login_completed"
        assert cache.get(f"login_fail:{email_hash}") is None
        assert user.id

    def test_login_rate_limiter_cache_failure_fails_closed(self, monkeypatch):
        def unavailable(*args, **kwargs):
            raise RuntimeError("cache down")

        monkeypatch.setattr("django_app.identity.throttles.cache.get", unavailable)

        response = self.client.post(
            reverse("login"),
            {"email": "cache-failure@example.com", "password": "WrongPass1"},
            format="json",
        )

        assert response.status_code == 429
        assert response.data["code"] == "login_rate_limited"

    def test_login_failure_logs_do_not_include_raw_secrets(self, caplog):
        caplog.set_level(logging.INFO, logger="django_app.identity.throttles")

        response = self.client.post(
            reverse("login"),
            {"email": "secret-log@example.com", "password": "DoNotLogPass1"},
            format="json",
        )

        assert response.status_code == 401
        assert "secret-log@example.com" not in caplog.text
        assert "DoNotLogPass1" not in caplog.text

    def test_login_mfa_required_uses_standard_contract(self):
        user = DjangoUser.objects.create_user(
            email="mfa-required@example.com",
            password="StrongPass1",
            first_name="Mfa",
            last_name="Required",
            role="planner",
        )
        user.totp_secret = "JBSWY3DPEHPK3PXP"
        user.two_factor_enabled = True
        user.save(update_fields=["totp_secret", "two_factor_enabled"])

        response = self.client.post(
            reverse("login"),
            {"email": "mfa-required@example.com", "password": "StrongPass1"},
            format="json",
        )

        assert response.status_code == 200
        assert response.data["success"] is True
        assert response.data["code"] == "mfa_required"
        assert response.data["data"]["requires_2fa"] is True
        assert response.data["data"]["temp_token"]

    def test_login_two_factor_invalid_code_uses_standard_contract(self):
        user = DjangoUser.objects.create_user(
            email="mfa-invalid@example.com",
            password="StrongPass1",
            first_name="Mfa",
            last_name="Invalid",
            role="planner",
            totp_secret="JBSWY3DPEHPK3PXP",
            two_factor_enabled=True,
        )
        temp_token = JWTTokenService().create_temp_token(str(user.id))

        response = self.client.post(
            reverse("2fa-login"),
            {"temp_token": temp_token, "token": "000000"},
            format="json",
        )

        assert response.status_code == 401
        assert response.data["success"] is False
        assert response.data["code"] == "invalid_mfa_code"
        assert response.data["field_errors"]["token"] == ["Invalid verification code."]

    @override_settings(REST_FRAMEWORK=_auth_throttle_rates(two_factor_ip="1/min"))
    def test_two_factor_ip_throttle_blocks_repeated_attempts(self):
        response = self.client.post(
            reverse("2fa-login"),
            {"temp_token": "bad-temp-token-a", "token": "000000"},
            format="json",
            REMOTE_ADDR="198.51.100.10",
        )
        assert response.status_code == 401

        response = self.client.post(
            reverse("2fa-login"),
            {"temp_token": "bad-temp-token-b", "token": "000000"},
            format="json",
            REMOTE_ADDR="198.51.100.10",
        )

        assert response.status_code == 429
        assert response.data["code"] == "mfa_rate_limited"

    @override_settings(REST_FRAMEWORK=_auth_throttle_rates(two_factor_temp_token="1/min"))
    def test_two_factor_temp_token_throttle_blocks_repeated_token_attempts(self):
        response = self.client.post(
            reverse("2fa-login"),
            {"temp_token": "same-bad-temp-token", "token": "000000"},
            format="json",
            REMOTE_ADDR="198.51.100.20",
        )
        assert response.status_code == 401

        response = self.client.post(
            reverse("2fa-login"),
            {"temp_token": "same-bad-temp-token", "token": "000000"},
            format="json",
            REMOTE_ADDR="198.51.100.21",
        )

        assert response.status_code == 429
        assert response.data["code"] == "mfa_rate_limited"

    @override_settings(MFA_FAILURE_LOCKOUT_THRESHOLD=2, MFA_FAILURE_LOCKOUT_SECONDS=900)
    def test_two_factor_progressive_lockout_blocks_after_failures(self):
        for _ in range(2):
            response = self.client.post(
                reverse("2fa-login"),
                {"temp_token": "progressive-bad-token", "token": "000000"},
                format="json",
            )
            assert response.status_code == 401

        response = self.client.post(
            reverse("2fa-login"),
            {"temp_token": "progressive-bad-token", "token": "000000"},
            format="json",
        )

        assert response.status_code == 429
        assert response.data["code"] == "mfa_rate_limited"

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
        assert response.data["success"] is True
        assert response.data["code"] == "profile_loaded"
        assert response.data["data"]["user"]["email"] == "profile@example.com"
        assert response.data["data"]["user"]["role"] == "planner"
        assert response.data["data"]["user"]["requires_password_setup"] is False

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
        assert response.data["success"] is True
        assert response.data["code"] == "profile_updated"
        assert response.data["data"]["user"]["first_name"] == "Updated"
        assert response.data["data"]["user"]["requires_password_setup"] is False
        assert response.data["data"]["user"]["has_password"] is True

    def test_setup_password_success_uses_standard_contract(self):
        user = DjangoUser.objects.create_user(
            email="setup-contract@example.com",
            password=None,
            first_name="Setup",
            last_name="Contract",
            role="vendor",
        )
        self.client.force_authenticate(user=user)

        response = self.client.post(
            reverse("setup-password"),
            {"password": "StrongPass1"},
            format="json",
        )

        assert response.status_code == 200
        assert response.data["success"] is True
        assert response.data["code"] == "password_setup_completed"
        assert response.data["data"]["user"]["email"] == "setup-contract@example.com"
        assert response.data["data"]["requires_password_setup"] is False
        assert response.data["data"]["next_path"] == "/vendor/dashboard"

    @override_settings(REST_FRAMEWORK=_auth_throttle_rates(register_ip="1/hour"))
    def test_register_ip_throttle_blocks_account_spam(self):
        first_response = self.client.post(
            reverse("register"),
            {
                "email": "register-ip-one@example.com",
                "password": "StrongPass1",
                "first_name": "One",
                "last_name": "User",
                "role": "planner",
            },
            format="json",
            REMOTE_ADDR="192.0.2.10",
        )
        assert first_response.status_code == 201

        response = self.client.post(
            reverse("register"),
            {
                "email": "register-ip-two@example.net",
                "password": "StrongPass1",
                "first_name": "Two",
                "last_name": "User",
                "role": "planner",
            },
            format="json",
            REMOTE_ADDR="192.0.2.10",
        )

        assert response.status_code == 429
        assert response.data["code"] == "registration_rate_limited"

    @override_settings(REST_FRAMEWORK=_auth_throttle_rates(register_email_domain="1/hour"))
    def test_register_email_domain_throttle_blocks_domain_bursts(self):
        first_response = self.client.post(
            reverse("register"),
            {
                "email": "domain-one@example.org",
                "password": "StrongPass1",
                "first_name": "One",
                "last_name": "User",
                "role": "planner",
            },
            format="json",
            REMOTE_ADDR="192.0.2.20",
        )
        assert first_response.status_code == 201

        response = self.client.post(
            reverse("register"),
            {
                "email": "domain-two@example.org",
                "password": "StrongPass1",
                "first_name": "Two",
                "last_name": "User",
                "role": "planner",
            },
            format="json",
            REMOTE_ADDR="192.0.2.21",
        )

        assert response.status_code == 429
        assert response.data["code"] == "registration_rate_limited"

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
        assert response.data["success"] is True
        assert response.data["code"] == "token_refreshed"
        assert "access" in response.data["data"]
        assert "user" in response.data["data"]
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
        assert response.data["success"] is True
        assert response.data["code"] == "token_refreshed"
        assert "access" in response.data["data"]
        assert "user" in response.data["data"]

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
        assert response.data["success"] is True
        assert response.data["code"] == "session_revoked"
        assert response.data["data"] == {}
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

        def capture_delay(user_id, token, delivery_id):
            enqueued["user_id"] = user_id
            enqueued["token"] = token
            enqueued["delivery_id"] = delivery_id

        monkeypatch.setattr("tasks.email_tasks.send_password_reset_email_task.delay", capture_delay)

        response = self.client.post(reverse("forgot-password"), {"email": "reset@example.com"}, format="json")

        assert response.status_code == 202
        assert response.data == FORGOT_PASSWORD_SUCCESS_RESPONSE
        assert enqueued["user_id"]
        assert enqueued["token"]
        assert enqueued["delivery_id"]
        delivery = PasswordResetEmailDelivery.objects.get(id=enqueued["delivery_id"])
        assert delivery.status == PasswordResetEmailDelivery.Status.QUEUED
        assert delivery.user.email == "reset@example.com"
        assert delivery.email_hash != "reset@example.com"
        assert delivery.email_domain == "example.com"
        reset_token_record = PasswordResetToken.objects.get(user_id=enqueued["user_id"])
        assert reset_token_record.status == PasswordResetToken.Status.ACTIVE
        assert reset_token_record.jti
        assert reset_token_record.token_hash != enqueued["token"]
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
        assert response.data == FORGOT_PASSWORD_SUCCESS_RESPONSE
        assert mail.outbox == []
        assert enqueued == []
        assert PasswordResetEmailDelivery.objects.count() == 0

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
        assert response.data == FORGOT_PASSWORD_SUCCESS_RESPONSE
        assert mail.outbox == []
        assert enqueued == []
        assert PasswordResetEmailDelivery.objects.count() == 0

    def test_forgot_password_validation_error_uses_standard_contract(self):
        response = self.client.post(reverse("forgot-password"), {"email": "not-an-email"}, format="json")

        assert response.status_code == 400
        assert response.data["success"] is False
        assert response.data["code"] == "password_recovery_validation_failed"
        assert response.data["message"] == "Please fix the highlighted fields."
        assert "email" in response.data["field_errors"]

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

        def capture_delay(user_id, token, delivery_id):
            enqueued["user_id"] = user_id
            enqueued["token"] = token
            enqueued["delivery_id"] = delivery_id

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
        assert response.data == FORGOT_PASSWORD_SUCCESS_RESPONSE
        assert mail.outbox == []
        assert "password_reset_email_dispatch_failed" in caplog.text
        assert "forgot_password_email_dispatch_deferred" in caplog.text
        delivery = PasswordResetEmailDelivery.objects.get()
        assert delivery.status == PasswordResetEmailDelivery.Status.DEFERRED
        assert delivery.failure_reason == "RuntimeError"
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
        delivery = _create_delivery(user)

        result = send_password_reset_email_task.apply(args=[str(user.id), token, str(delivery.id)]).get()

        assert result is True
        delivery.refresh_from_db()
        assert delivery.status == PasswordResetEmailDelivery.Status.SENT
        assert delivery.attempts == 1
        assert delivery.sent_at is not None
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
    def test_password_reset_email_delivery_failure_is_recorded(self, monkeypatch, caplog):
        user = DjangoUser.objects.create_user(
            email="task-fail@example.com",
            password="StrongPass1",
            first_name="Task",
            last_name="Fail",
            role="planner",
        )
        delivery = _create_delivery(user)
        token = JWTTokenService().create_password_reset_token(str(user.id))

        def fail_send_mail(*args, **kwargs):
            raise RuntimeError("provider unavailable")

        monkeypatch.setattr("django_app.identity.password_reset_email.send_mail", fail_send_mail)
        caplog.set_level(logging.ERROR, logger="django_app.identity.password_reset_email")

        with pytest.raises(RuntimeError):
            send_password_reset_email(str(user.id), token, delivery_id=str(delivery.id), task_id="task-1", attempt=2)

        delivery.refresh_from_db()
        assert delivery.status == PasswordResetEmailDelivery.Status.FAILED
        assert delivery.failure_reason == "RuntimeError"
        assert delivery.attempts == 2
        assert delivery.failed_at is not None
        assert "password_reset_email_failed" in caplog.text
        assert token not in caplog.text
        assert "task-fail@example.com" not in caplog.text

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
        assert response.data["success"] is False
        assert response.data["code"] == "password_reset_validation_failed"
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
        assert response.data["success"] is False
        assert response.data["code"] == "password_reset_validation_failed"
        assert response.data["message"] == "Please fix the highlighted fields."
        assert "new_password" in response.data["field_errors"]

    def test_reset_password_invalid_token_returns_token_invalid_response(self):
        response = self.client.post(
            reverse("reset-password"),
            {"token": "not-a-valid-token", "new_password": "ValidPass1!"},
            format="json",
        )

        assert response.status_code == 400
        assert response.data == PASSWORD_RESET_TOKEN_INVALID_RESPONSE

    def test_reset_password_missing_user_returns_same_token_invalid_response(self):
        token = JWTTokenService().create_password_reset_token(str(uuid.uuid4()))

        response = self.client.post(
            reverse("reset-password"),
            {"token": token, "new_password": "ValidPass1!"},
            format="json",
        )

        assert response.status_code == 400
        assert response.data == PASSWORD_RESET_TOKEN_INVALID_RESPONSE

    def test_reset_password_inactive_user_returns_same_token_invalid_response(self):
        user = DjangoUser.objects.create_user(
            email="inactive-reset@example.com",
            password="StrongPass1!",
            first_name="Inactive",
            last_name="Reset",
            role="planner",
            is_active=False,
        )
        token = _issue_reset_token(user)

        response = self.client.post(
            reverse("reset-password"),
            {"token": token, "new_password": "ValidPass1!"},
            format="json",
        )

        assert response.status_code == 400
        assert response.data == PASSWORD_RESET_TOKEN_INVALID_RESPONSE

    def test_reset_password_valid_token_resets_password_successfully(self):
        user = DjangoUser.objects.create_user(
            email="valid-reset@example.com",
            password="OldPass1!",
            first_name="Valid",
            last_name="Reset",
            role="planner",
        )
        token = _issue_reset_token(user)

        response = self.client.post(
            reverse("reset-password"),
            {"token": token, "new_password": "NewValidPass1!"},
            format="json",
        )

        user.refresh_from_db()
        reset_token = PasswordResetToken.objects.get(user=user)
        assert response.status_code == 200
        assert response.data == {
            "success": True,
            "code": "password_reset_completed",
            "message": "Password updated successfully.",
            "data": {"status": "password_reset"},
            "status": "password_reset",
        }
        assert user.check_password("NewValidPass1!") is True
        assert reset_token.status == PasswordResetToken.Status.USED
        assert reset_token.used_at is not None
        assert reset_token.used_ip_hash

    def test_reset_password_token_cannot_be_reused(self):
        user = DjangoUser.objects.create_user(
            email="reuse-reset@example.com",
            password="OldPass1!",
            first_name="Reuse",
            last_name="Reset",
            role="planner",
        )
        token = _issue_reset_token(user)

        first_response = self.client.post(
            reverse("reset-password"),
            {"token": token, "new_password": "NewValidPass1!"},
            format="json",
        )
        second_response = self.client.post(
            reverse("reset-password"),
            {"token": token, "new_password": "AnotherValidPass1!"},
            format="json",
        )

        user.refresh_from_db()
        reset_token = PasswordResetToken.objects.get(user=user)
        assert first_response.status_code == 200
        assert second_response.status_code == 400
        assert second_response.data == PASSWORD_RESET_TOKEN_INVALID_RESPONSE
        assert user.check_password("NewValidPass1!") is True
        assert reset_token.status == PasswordResetToken.Status.USED

    def test_reset_password_revoked_and_expired_tokens_share_invalid_response(self):
        user = DjangoUser.objects.create_user(
            email="invalid-state-reset@example.com",
            password="OldPass1!",
            first_name="Invalid",
            last_name="State",
            role="planner",
        )
        revoked_token = _issue_reset_token(user)
        PasswordResetToken.objects.filter(user=user).update(status=PasswordResetToken.Status.REVOKED)
        expired_token = _issue_reset_token(user)
        PasswordResetToken.objects.filter(user=user, status=PasswordResetToken.Status.ACTIVE).update(
            expires_at=timezone.now() - timedelta(minutes=1)
        )

        revoked_response = self.client.post(
            reverse("reset-password"),
            {"token": revoked_token, "new_password": "ValidPass1!"},
            format="json",
        )
        expired_response = self.client.post(
            reverse("reset-password"),
            {"token": expired_token, "new_password": "ValidPass1!"},
            format="json",
        )

        assert revoked_response.status_code == 400
        assert expired_response.status_code == 400
        assert revoked_response.data == expired_response.data
        assert revoked_response.data == PASSWORD_RESET_TOKEN_INVALID_RESPONSE

    def test_new_reset_request_revokes_previous_active_token(self):
        user = DjangoUser.objects.create_user(
            email="new-link-reset@example.com",
            password="OldPass1!",
            first_name="New",
            last_name="Link",
            role="planner",
        )
        first_token = _issue_reset_token(user)
        second_token = _issue_reset_token(user)

        first_record = PasswordResetToken.objects.get(token_hash=password_reset_token_hash(first_token))
        second_record = PasswordResetToken.objects.get(token_hash=password_reset_token_hash(second_token))

        assert first_record.status == PasswordResetToken.Status.REVOKED
        assert second_record.status == PasswordResetToken.Status.ACTIVE

    def test_password_reset_token_raw_value_is_not_stored_or_logged(self, caplog):
        user = DjangoUser.objects.create_user(
            email="raw-token-reset@example.com",
            password="OldPass1!",
            first_name="Raw",
            last_name="Token",
            role="planner",
        )
        caplog.set_level(logging.INFO, logger="infrastructure.adapters.jwt_token_service")

        token = _issue_reset_token(user)

        record = PasswordResetToken.objects.get(user=user)
        stored_values = [str(record.jti), record.token_hash]
        assert token not in stored_values
        assert token not in caplog.text
        assert "/auth/reset-password?token=" not in caplog.text

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
        inactive_user_token = _issue_reset_token(inactive_user)

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
