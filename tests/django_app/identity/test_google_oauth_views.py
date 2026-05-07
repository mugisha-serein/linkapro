from dataclasses import dataclass

import pytest
from django.urls import reverse
from rest_framework.test import APIClient


@dataclass
class _UseCaseResult:
    requires_2fa: bool
    temp_token: str | None = None
    access: str | None = None
    refresh: str | None = None


class _AdapterStub:
    def __init__(self, auth_url="https://accounts.google.com/fake-auth"):
        self._auth_url = auth_url

    def build_auth_url(self):
        return self._auth_url

    def exchange_code(self, code):
        return {"access_token": "google_access", "refresh_token": "google_refresh", "expires_in": 3600}

    def get_user_info(self, access_token):
        return {
            "email": "oauth@example.com",
            "google_id": "google-123",
            "name": "OAuth User",
            "picture": "",
        }


class _UseCaseStub:
    def __init__(self, result):
        self._result = result

    def execute(self, user_data, token_data):
        return self._result


@pytest.mark.django_db
class TestGoogleOAuthViews:
    @pytest.fixture(autouse=True)
    def setup(self):
        self.client = APIClient()

    def test_google_login_redirects_to_google_auth(self, monkeypatch):
        from django_app.identity import views

        monkeypatch.setattr(
            views,
            "get_google_oauth_adapter",
            lambda: _AdapterStub(auth_url="https://accounts.google.com/fake-auth"),
        )

        response = self.client.get(reverse("google-login"))
        assert response.status_code == 302
        assert response.url == "https://accounts.google.com/fake-auth"

    def test_google_callback_missing_code_redirects_error(self, settings):
        settings.DEBUG = True
        settings.FRONTEND_URL = "http://localhost:3000"
        response = self.client.get(reverse("google-callback"))
        assert response.status_code == 302
        assert response.url == "http://localhost:3000/auth/error?reason=missing_code"

    def test_google_callback_redirects_to_2fa_when_required(self, monkeypatch, settings):
        from django_app.identity import views

        settings.DEBUG = True
        settings.FRONTEND_URL = "http://localhost:3000"
        monkeypatch.setattr(views, "get_google_oauth_adapter", lambda: _AdapterStub())
        monkeypatch.setattr(
            views,
            "get_google_login_use_case",
            lambda: _UseCaseStub(
                _UseCaseResult(requires_2fa=True, temp_token="temp-abc")
            ),
        )

        response = self.client.get(reverse("google-callback"), {"code": "oauth-code"})
        assert response.status_code == 302
        assert response.url == "http://localhost:3000/2fa/verify?temp_token=temp-abc"

    def test_google_callback_redirects_success_with_tokens(self, monkeypatch, settings):
        from django_app.identity import views

        settings.DEBUG = True
        settings.FRONTEND_URL = "http://localhost:3000"
        monkeypatch.setattr(views, "get_google_oauth_adapter", lambda: _AdapterStub())
        monkeypatch.setattr(
            views,
            "get_google_login_use_case",
            lambda: _UseCaseStub(
                _UseCaseResult(
                    requires_2fa=False,
                    access="access-token",
                    refresh="refresh-token",
                )
            ),
        )

        response = self.client.get(reverse("google-callback"), {"code": "oauth-code"})
        assert response.status_code == 302
        assert (
            response.url
            == "http://localhost:3000/auth/success?access=access-token&refresh=refresh-token"
        )

    def test_google_callback_rejects_non_https_frontend_in_production(self, settings):
        settings.DEBUG = False
        settings.FRONTEND_URL = "http://localhost:3000"

        with pytest.raises(ValueError, match="HTTPS"):
            self.client.get(reverse("google-callback"), {"code": "oauth-code"})
