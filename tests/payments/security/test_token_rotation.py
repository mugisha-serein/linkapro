import uuid
import pytest
from unittest.mock import MagicMock, ANY
from payments.application.token_handlers import TokenCommandHandlers

pytestmark = pytest.mark.django_db

# 32‑byte secret to avoid InsecureKeyLengthWarning
TEST_SECRET = "test-secret-key-for-jwt-32bytes!"


class TestTokenRotation:
    @pytest.fixture
    def blacklist(self):
        return MagicMock()

    @pytest.fixture
    def handler(self, blacklist):
        return TokenCommandHandlers(blacklist)

    def _create_refresh_token_str(self, user_id=None, jti=None, family=None, step_up=False, scope="", env="test"):
        from rest_framework_simplejwt.tokens import RefreshToken
        token = RefreshToken()
        token["user_id"] = user_id or str(uuid.uuid4())
        token["jti"] = jti or str(uuid.uuid4())
        if family is not None:
            token["family"] = family
        token["step_up"] = step_up
        token["scope"] = scope
        token["env"] = env
        return str(token), token.payload

    def test_rotation_returns_new_tokens(self, handler, blacklist, settings):
        settings.SECRET_KEY = TEST_SECRET
        settings.SIMPLE_JWT = {"SIGNING_KEY": TEST_SECRET, "ALGORITHM": "HS256"}

        blacklist.is_blacklisted.return_value = False
        old_refresh_str, _ = self._create_refresh_token_str()

        new_access, new_refresh = handler.refresh_access_token(old_refresh_str)

        # Tokens must differ from the old one
        assert new_access != old_refresh_str
        assert new_refresh != old_refresh_str

        # Verify that the old token was blacklisted (at least once)
        blacklist.blacklist.assert_called()

    def test_rotation_preserves_user_id(self, handler, blacklist, settings):
        settings.SECRET_KEY = TEST_SECRET
        settings.SIMPLE_JWT = {"SIGNING_KEY": TEST_SECRET, "ALGORITHM": "HS256"}

        blacklist.is_blacklisted.return_value = False
        user_id = str(uuid.uuid4())
        old_refresh_str, _ = self._create_refresh_token_str(user_id=user_id)
        new_access, _ = handler.refresh_access_token(old_refresh_str)

        from rest_framework_simplejwt.tokens import AccessToken
        decoded = AccessToken(new_access)
        assert decoded["user_id"] == user_id

    def test_invalid_refresh_token_raises(self, handler, blacklist):
        with pytest.raises(ValueError, match="Invalid refresh token"):
            handler.refresh_access_token("invalid_token_string")
        blacklist.blacklist.assert_not_called()