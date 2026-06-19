from unittest.mock import MagicMock, patch

import pytest
from django.test import RequestFactory, override_settings
from rest_framework_simplejwt.exceptions import InvalidToken

from payments.infrastructure.authentication import HardenedJWTAuthentication


pytestmark = pytest.mark.django_db


class TestHardenedJWTAuthentication:
    @pytest.fixture
    def factory(self):
        return RequestFactory()

    @override_settings(TOKEN_ENV="test", PAYMENT_ENV="live")
    @patch("payments.infrastructure.authentication.RedisTokenBlacklist")
    @patch("payments.infrastructure.authentication.JWTAuthentication.authenticate")
    def test_accepts_token_with_matching_env(self, mock_super, mock_blacklist, factory):
        user = MagicMock()
        token = {"jti": "jti-1", "env": "test"}
        mock_super.return_value = (user, token)
        mock_blacklist.return_value.is_blacklisted.return_value = False

        auth = HardenedJWTAuthentication()
        result = auth.authenticate(factory.get("/api/django/identity/profile/"))

        assert result == (user, token)
        mock_blacklist.return_value.is_blacklisted.assert_called_once_with("jti-1")

    @override_settings(TOKEN_ENV="live")
    @patch("payments.infrastructure.authentication.RedisTokenBlacklist")
    @patch("payments.infrastructure.authentication.JWTAuthentication.authenticate")
    def test_rejects_token_missing_env(self, mock_super, mock_blacklist, factory):
        user = MagicMock()
        token = {"jti": "jti-2"}
        mock_super.return_value = (user, token)
        mock_blacklist.return_value.is_blacklisted.return_value = False

        auth = HardenedJWTAuthentication()

        with pytest.raises(InvalidToken, match="environment"):
            auth.authenticate(factory.get("/api/django/identity/profile/"))

    @override_settings(TOKEN_ENV="production", PAYMENT_ENV="test", ACCEPT_LEGACY_PAYMENT_ENV_TOKENS=True)
    @patch("payments.infrastructure.authentication.RedisTokenBlacklist")
    @patch("payments.infrastructure.authentication.JWTAuthentication.authenticate")
    def test_accepts_legacy_payment_env_token_during_transition(self, mock_super, mock_blacklist, factory):
        user = MagicMock()
        token = {"jti": "jti-legacy", "env": "test"}
        mock_super.return_value = (user, token)
        mock_blacklist.return_value.is_blacklisted.return_value = False

        auth = HardenedJWTAuthentication()
        result = auth.authenticate(factory.get("/api/django/identity/profile/"))

        assert result == (user, token)

    @override_settings(TOKEN_ENV="production", PAYMENT_ENV="test", ACCEPT_LEGACY_PAYMENT_ENV_TOKENS=False)
    @patch("payments.infrastructure.authentication.RedisTokenBlacklist")
    @patch("payments.infrastructure.authentication.JWTAuthentication.authenticate")
    def test_rejects_legacy_payment_env_token_when_disabled(self, mock_super, mock_blacklist, factory):
        user = MagicMock()
        token = {"jti": "jti-legacy", "env": "test"}
        mock_super.return_value = (user, token)
        mock_blacklist.return_value.is_blacklisted.return_value = False

        auth = HardenedJWTAuthentication()

        with pytest.raises(InvalidToken, match="environment"):
            auth.authenticate(factory.get("/api/django/identity/profile/"))
