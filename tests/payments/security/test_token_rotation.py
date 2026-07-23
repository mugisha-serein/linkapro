import uuid
import pytest
from unittest.mock import MagicMock, ANY
from application.identity.token_handlers import TokenCommandHandlers

pytestmark = pytest.mark.django_db

# 32‑byte secret to avoid InsecureKeyLengthWarning
TEST_SECRET = "test-secret-key-for-jwt-32bytes!"


class TestTokenRotation:
    @pytest.fixture(autouse=True)
    def token_env(self, settings):
        settings.TOKEN_ENV = "test"
        settings.PAYMENT_ENV = "test"
        settings.ACCEPT_LEGACY_PAYMENT_ENV_TOKENS = True

    @pytest.fixture
    def blacklist(self):
        mock = MagicMock()
        mock.is_blacklisted.return_value = False
        mock.is_family_blacklisted.return_value = False
        return mock

    @pytest.fixture
    def session_store(self):
        mock = MagicMock()
        mock.is_token_revoked_for_user.return_value = False
        mock.token_version_matches_active_user.return_value = True
        mock.active_user_bootstrap_claims.side_effect = (
            lambda user_id, session_id=None: {
                "id": str(user_id),
                "email": "user@example.com",
                "role": "planner",
                "first_name": "Test",
                "last_name": "User",
                "is_active": True,
                "is_verified": True,
                "has_password": True,
                "requires_password_setup": False,
                "two_factor_enabled": False,
                "auth_token_version": 0,
                "is_authenticated": True,
                **({"session_id": str(session_id)} if session_id else {}),
            }
        )
        return mock

    @pytest.fixture
    def handler(self, blacklist, session_store):
        return TokenCommandHandlers(blacklist, session_store=session_store)

    def _create_refresh_token_str(self, user_id=None, jti=None, family=None, step_up=False, scope="", env="test"):
        from rest_framework_simplejwt.tokens import RefreshToken
        token = RefreshToken()
        token["user_id"] = user_id or str(uuid.uuid4())
        token["jti"] = jti or str(uuid.uuid4())
        token["family"] = family or str(uuid.uuid4())
        token["step_up"] = step_up
        token["scope"] = scope
        token["env"] = env
        return str(token), token.payload

    def test_rotation_returns_new_tokens(self, handler, blacklist, settings):
        settings.SECRET_KEY = TEST_SECRET
        settings.SIMPLE_JWT = {"SIGNING_KEY": TEST_SECRET, "ALGORITHM": "HS256"}

        blacklist.is_blacklisted.return_value = False
        old_refresh_str, _ = self._create_refresh_token_str()

        new_access, new_refresh, _ = handler.refresh_access_token(old_refresh_str)

        # Tokens must differ from the old one
        assert new_access != old_refresh_str
        assert new_refresh != old_refresh_str

        # Verify that the old token was blacklisted (at least once)
        blacklist.blacklist.assert_called()
        blacklist.blacklist_family.assert_not_called()

    def test_rotation_preserves_user_id(self, handler, blacklist, settings):
        settings.SECRET_KEY = TEST_SECRET
        settings.SIMPLE_JWT = {"SIGNING_KEY": TEST_SECRET, "ALGORITHM": "HS256"}

        blacklist.is_blacklisted.return_value = False
        user_id = str(uuid.uuid4())
        old_refresh_str, payload = self._create_refresh_token_str(user_id=user_id)
        new_access, _, _ = handler.refresh_access_token(old_refresh_str)

        from rest_framework_simplejwt.tokens import AccessToken
        decoded = AccessToken(new_access)
        assert decoded["user_id"] == user_id
        assert decoded["env"] == "test"
        assert decoded["family"] == payload["family"]

    def test_invalid_refresh_token_raises(self, handler, blacklist):
        with pytest.raises(ValueError, match="Invalid refresh token"):
            handler.refresh_access_token("invalid_token_string")
        blacklist.blacklist.assert_not_called()

    def test_revoke_refresh_token_blacklists_jti_and_family(self, handler, blacklist):
        refresh_str, payload = self._create_refresh_token_str()

        handler.revoke_refresh_token(refresh_str)

        blacklist.blacklist.assert_called_once()
        blacklist.blacklist_family.assert_called_once_with(payload["family"])

    def test_legacy_payment_env_refresh_rotates_to_token_env(self, handler, blacklist, settings):
        settings.TOKEN_ENV = "production"
        settings.PAYMENT_ENV = "test"
        settings.ACCEPT_LEGACY_PAYMENT_ENV_TOKENS = True
        settings.SECRET_KEY = TEST_SECRET
        settings.SIMPLE_JWT = {"SIGNING_KEY": TEST_SECRET, "ALGORITHM": "HS256"}

        refresh_str, _ = self._create_refresh_token_str(env="test")

        new_access, new_refresh, _ = handler.refresh_access_token(refresh_str)

        from rest_framework_simplejwt.tokens import AccessToken, RefreshToken
        assert AccessToken(new_access)["env"] == "production"
        assert RefreshToken(new_refresh)["env"] == "production"

    def test_legacy_payment_env_refresh_rejected_when_disabled(self, handler, blacklist, settings):
        settings.TOKEN_ENV = "production"
        settings.PAYMENT_ENV = "test"
        settings.ACCEPT_LEGACY_PAYMENT_ENV_TOKENS = False
        settings.SECRET_KEY = TEST_SECRET
        settings.SIMPLE_JWT = {"SIGNING_KEY": TEST_SECRET, "ALGORITHM": "HS256"}

        refresh_str, _ = self._create_refresh_token_str(env="test")

        with pytest.raises(ValueError, match="Token environment mismatch"):
            handler.refresh_access_token(refresh_str)
        blacklist.blacklist.assert_not_called()

    def test_missing_family_rejected(self, handler, blacklist):
        from rest_framework_simplejwt.tokens import RefreshToken
        token = RefreshToken()
        token["user_id"] = str(uuid.uuid4())
        token["jti"] = str(uuid.uuid4())
        token["env"] = "test"

        with pytest.raises(ValueError, match="family"):
            handler.refresh_access_token(str(token))
        blacklist.blacklist.assert_not_called()
