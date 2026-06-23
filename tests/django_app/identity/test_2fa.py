import pytest
from django.urls import reverse
from rest_framework.test import APIClient
import pyotp

from django_app.identity.models import User

pytestmark = pytest.mark.django_db


class TestTwoFactor:
    @pytest.fixture(autouse=True)
    def setup(self):
        self.client = APIClient()

    def test_enable_2fa_returns_secret_and_qr(self):
        user = User.objects.create_user(
            email="t@t.com",
            password="StrongPass1",
            first_name="T",
            last_name="User",
            role="planner",
        )
        self.client.force_authenticate(user=user)
        url = reverse("2fa-enable")
        response = self.client.post(url)
        assert response.status_code == 200
        assert response.data["success"] is True
        assert response.data["code"] == "mfa_setup_started"
        assert "secret" in response.data["data"]
        assert "provisioning_uri" in response.data["data"]

    def test_verify_setup_with_valid_code(self):
        user = User.objects.create_user(
            email="t@t.com",
            password="StrongPass1",
            first_name="T",
            last_name="User",
            role="planner",
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
        )
        user.totp_secret = secret
        user.two_factor_enabled = True
        user.password_hash = None  # ensure we use Django's password (set_password not used here? Actually create_user hashes the password, so good)
        user.save()

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
