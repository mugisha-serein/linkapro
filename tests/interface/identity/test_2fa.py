from copy import deepcopy

import pytest
from django.conf import settings as django_settings
from django.core.cache import cache
from django.test import override_settings
from django.utils import timezone
from django.urls import reverse
from rest_framework.test import APIClient
import pyotp

from domain.identity.mfa import TOTPSecret
from interface.identity.models import User
from infrastructure.identity.django_user_repository import DjangoUserRepository

pytestmark = pytest.mark.django_db


def _mfa_enrollment_throttle_config(rate: str) -> dict:
    config = deepcopy(django_settings.REST_FRAMEWORK)
    config["DEFAULT_THROTTLE_RATES"] = {
        **config.get("DEFAULT_THROTTLE_RATES", {}),
        "two_factor_enrollment": rate,
    }
    return config


class _KeyProvider:
    def wrap_dek(self, dek: bytes) -> bytes:
        return dek

    def unwrap_dek(self, encrypted_dek: bytes) -> bytes:
        return encrypted_dek


class TestTwoFactor:
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

            def is_mfa_grant_blacklisted(self, grant):
                return self.is_blacklisted(grant.grant_id)

            def blacklist_mfa_grant(self, grant):
                self.blacklist(grant.grant_id, grant.remaining_ttl_seconds(now=timezone.now()))

        def django_user_repository_factory():
            return DjangoUserRepository(key_provider=_KeyProvider())

        monkeypatch.setattr("interface.identity.services.DjangoUserRepository", django_user_repository_factory)
        monkeypatch.setattr("interface.identity.services.RedisTokenBlacklist", InMemoryTokenBlacklist)
        self.repo = DjangoUserRepository(key_provider=_KeyProvider())
        self.client = APIClient()

    def test_enable_2fa_returns_secret_and_qr(self):
        user = User.objects.create_user(
            email="t@t.com",
            password="StrongPass1",
            first_name="T",
            last_name="User",
            role="planner",
            is_verified=True,
        )
        self.client.force_authenticate(user=user)
        url = reverse("2fa-enable")
        response = self.client.post(url)
        assert response.status_code == 200
        assert response.data["success"] is True
        assert response.data["code"] == "mfa_setup_started"
        assert "secret" in response.data["data"]
        assert "provisioning_uri" in response.data["data"]

    def test_enable_2fa_is_throttled_by_user_and_ip(self):
        cache.clear()
        user = User.objects.create_user(
            email="mfa-enable-throttle@example.com",
            password="StrongPass1",
            first_name="T",
            last_name="User",
            role="planner",
            is_verified=True,
        )
        self.client.force_authenticate(user=user)
        url = reverse("2fa-enable")

        with override_settings(REST_FRAMEWORK=_mfa_enrollment_throttle_config("1/min")):
            first_response = self.client.post(url, REMOTE_ADDR="198.51.100.20")
            second_response = self.client.post(url, REMOTE_ADDR="198.51.100.20")

        assert first_response.status_code == 200
        assert second_response.status_code == 429
        assert second_response.data["code"] == "mfa_rate_limited"

    def test_verify_setup_with_valid_code(self):
        user = User.objects.create_user(
            email="t@t.com",
            password="StrongPass1",
            first_name="T",
            last_name="User",
            role="planner",
            is_verified=True,
        )
        self.client.force_authenticate(user=user)

        # Enable 2FA (gets secret)
        enable_url = reverse("2fa-enable")
        resp = self.client.post(enable_url)
        secret = resp.data["data"]["secret"]

        # Generate valid TOTP code
        totp = pyotp.TOTP(secret)
        valid_code = totp.now()

        # Verify setup
        verify_url = reverse("2fa-verify-setup")
        resp = self.client.post(verify_url, {"token": valid_code}, format="json")
        assert resp.status_code == 200
        assert resp.data["success"] is True
        assert resp.data["code"] == "mfa_enabled"

        user.refresh_from_db()
        assert user.two_factor_enabled is True

    def test_verify_2fa_setup_is_throttled_by_user_and_ip(self):
        cache.clear()
        user = User.objects.create_user(
            email="mfa-verify-throttle@example.com",
            password="StrongPass1",
            first_name="T",
            last_name="User",
            role="planner",
            is_verified=True,
        )
        self.client.force_authenticate(user=user)

        enable_response = self.client.post(reverse("2fa-enable"))
        secret = enable_response.data["data"]["secret"]
        token = pyotp.TOTP(secret).now()

        with override_settings(REST_FRAMEWORK=_mfa_enrollment_throttle_config("1/min")):
            first_response = self.client.post(
                reverse("2fa-verify-setup"),
                {"token": token},
                format="json",
                REMOTE_ADDR="198.51.100.21",
            )
            second_response = self.client.post(
                reverse("2fa-verify-setup"),
                {"token": token},
                format="json",
                REMOTE_ADDR="198.51.100.21",
            )

        assert first_response.status_code == 200
        assert second_response.status_code == 429
        assert second_response.data["code"] == "mfa_rate_limited"

    def test_login_with_2fa_flow(self, settings):
        # Ensure Django settings are available
        settings.SECRET_KEY = "test-secret-key-for-jwt-32bytes!"

        # Create user with 2FA enabled
        secret = pyotp.random_base32()
        user = User.objects.create_user(
            email="t@t.com",
            password="StrongPass1",
            first_name="T",
            last_name="User",
            role="planner",
            is_verified=True,
        )
        self.repo.set_totp_secret(user.id, TOTPSecret(secret))

        # Step 1: normal login should return temp token
        login_url = reverse("login")
        resp = self.client.post(
            login_url,
            {"email": "t@t.com", "password": "StrongPass1"},
            format="json",
        )
        assert resp.status_code == 200
        assert resp.data["success"] is True
        assert resp.data["code"] == "mfa_required"
        assert resp.data["data"]["requires_2fa"] is True
        temp_token = resp.data["data"]["temp_token"]

        # Step 2: complete 2FA
        code = pyotp.TOTP(secret).now()
        two_fa_url = reverse("2fa-login")
        resp = self.client.post(
            two_fa_url,
            {"temp_token": temp_token, "token": code},
            format="json",
        )
        assert resp.status_code == 200
        assert resp.data["success"] is True
        assert resp.data["code"] == "mfa_login_completed"
        assert "access" in resp.data["data"]
