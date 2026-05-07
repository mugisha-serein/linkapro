import pytest

from infrastructure.adapters.google_oauth_adapter import (
    GoogleOAuthAdapter,
    GoogleOAuthAdapterError,
)


class _Response:
    def __init__(self, ok, payload):
        self.ok = ok
        self._payload = payload

    def json(self):
        return self._payload


@pytest.mark.django_db
class TestGoogleOAuthAdapter:
    def test_build_auth_url_requires_https_in_production(self, settings):
        settings.DEBUG = False
        settings.GOOGLE_CLIENT_ID = "client-id"
        settings.GOOGLE_REDIRECT_URI = "http://localhost:8000/callback"

        adapter = GoogleOAuthAdapter()
        with pytest.raises(GoogleOAuthAdapterError, match="HTTPS"):
            adapter.build_auth_url()

    def test_exchange_code_rejects_audience_mismatch(self, settings, monkeypatch):
        settings.GOOGLE_CLIENT_ID = "expected-client-id"
        settings.GOOGLE_CLIENT_SECRET = "secret"
        settings.GOOGLE_REDIRECT_URI = "https://api.example.com/oauth/callback"

        adapter = GoogleOAuthAdapter()

        def fake_post(*args, **kwargs):
            return _Response(
                True,
                {
                    "access_token": "access",
                    "id_token": "id-token",
                    "expires_in": 3600,
                },
            )

        def fake_get(*args, **kwargs):
            return _Response(
                True,
                {
                    "aud": "wrong-client-id",
                    "iss": "https://accounts.google.com",
                    "exp": "9999999999",
                },
            )

        monkeypatch.setattr("infrastructure.adapters.google_oauth_adapter.requests.post", fake_post)
        monkeypatch.setattr("infrastructure.adapters.google_oauth_adapter.requests.get", fake_get)

        with pytest.raises(GoogleOAuthAdapterError, match="audience mismatch"):
            adapter.exchange_code("oauth-code")

    def test_exchange_code_rejects_issuer_mismatch(self, settings, monkeypatch):
        settings.GOOGLE_CLIENT_ID = "expected-client-id"
        settings.GOOGLE_CLIENT_SECRET = "secret"
        settings.GOOGLE_REDIRECT_URI = "https://api.example.com/oauth/callback"

        adapter = GoogleOAuthAdapter()

        def fake_post(*args, **kwargs):
            return _Response(
                True,
                {
                    "access_token": "access",
                    "id_token": "id-token",
                    "expires_in": 3600,
                },
            )

        def fake_get(*args, **kwargs):
            return _Response(
                True,
                {
                    "aud": "expected-client-id",
                    "iss": "malicious-issuer",
                    "exp": "9999999999",
                },
            )

        monkeypatch.setattr("infrastructure.adapters.google_oauth_adapter.requests.post", fake_post)
        monkeypatch.setattr("infrastructure.adapters.google_oauth_adapter.requests.get", fake_get)

        with pytest.raises(GoogleOAuthAdapterError, match="issuer mismatch"):
            adapter.exchange_code("oauth-code")

    def test_exchange_code_successfully_validates_id_token(self, settings, monkeypatch):
        settings.GOOGLE_CLIENT_ID = "expected-client-id"
        settings.GOOGLE_CLIENT_SECRET = "secret"
        settings.GOOGLE_REDIRECT_URI = "https://api.example.com/oauth/callback"

        adapter = GoogleOAuthAdapter()

        def fake_post(*args, **kwargs):
            return _Response(
                True,
                {
                    "access_token": "access",
                    "id_token": "id-token",
                    "expires_in": 3600,
                },
            )

        def fake_get(*args, **kwargs):
            return _Response(
                True,
                {
                    "aud": "expected-client-id",
                    "iss": "https://accounts.google.com",
                    "exp": "9999999999",
                },
            )

        monkeypatch.setattr("infrastructure.adapters.google_oauth_adapter.requests.post", fake_post)
        monkeypatch.setattr("infrastructure.adapters.google_oauth_adapter.requests.get", fake_get)

        data = adapter.exchange_code("oauth-code")
        assert data["access_token"] == "access"

    def test_get_user_info_rejects_unverified_email(self, monkeypatch):
        adapter = GoogleOAuthAdapter()

        def fake_get(*args, **kwargs):
            return _Response(
                True,
                {
                    "sub": "google-123",
                    "email": "user@example.com",
                    "email_verified": False,
                },
            )

        monkeypatch.setattr("infrastructure.adapters.google_oauth_adapter.requests.get", fake_get)

        with pytest.raises(GoogleOAuthAdapterError, match="not verified"):
            adapter.get_user_info("access")
