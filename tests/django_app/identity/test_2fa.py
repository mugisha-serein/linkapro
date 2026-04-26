import pyotp
import pytest
from django.urls import reverse
from rest_framework.test import APIClient
from unittest.mock import patch
from django_app.identity.models import User

pytestmark = pytest.mark.django_db

class TestTwoFactor:
    def test_enable_2fa_returns_secret_and_qr(self, client):
        user = User.objects.create_user(email="t@t.com", password="p", role="planner")
        client.force_authenticate(user=user)
        url = reverse("2fa-enable")
        response = client.post(url)
        assert response.status_code == 200
        assert "secret" in response.data
        assert "provisioning_uri" in response.data

    def test_verify_setup_with_valid_code(self, client, settings):
        user = User.objects.create_user(email="t@t.com", password="p", role="planner")
        client.force_authenticate(user=user)
        # first enable
        enable_url = reverse("2fa-enable")
        resp = client.post(enable_url)
        secret = resp.data["secret"]
        # generate valid code
        import pyotp
        totp = pyotp.TOTP(secret)
        valid_code = totp.now()
        verify_url = reverse("2fa-verify-setup")
        resp = client.post(verify_url, {"token": valid_code})
        assert resp.status_code == 200
        user.refresh_from_db()
        assert user.two_factor_enabled is True

    def test_login_with_2fa_flow(self, client, settings):
        # create user with 2FA enabled
        user = User.objects.create_user(email="t@t.com", password="p", role="planner")
        secret = pyotp.random_base32()
        user.totp_secret = secret
        user.two_factor_enabled = True
        user.save()
        # first login attempt with password
        login_url = reverse("login")
        resp = client.post(login_url, {"email": "t@t.com", "password": "p"})
        assert resp.status_code == 200
        assert resp.data.get("requires_2fa") is True
        temp_token = resp.data["temp_token"]
        # second step: provide TOTP
        code = pyotp.TOTP(secret).now()
        two_fa_url = reverse("2fa-login")
        resp = client.post(two_fa_url, {"temp_token": temp_token, "token": code})
        assert resp.status_code == 200
        assert "access_token" in resp.data