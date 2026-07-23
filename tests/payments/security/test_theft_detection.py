import uuid
import pytest
from unittest.mock import MagicMock
from application.identity.token_handlers import TokenCommandHandlers

pytestmark = pytest.mark.django_db

# Use a key long enough to avoid InsecureKeyLengthWarning (32 bytes)
TEST_SECRET = "test-secret-key-for-jwt-32bytes!"  # 32 characters


class TestTheftDetection:
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
        mock.get_bootstrap_claims.side_effect = (
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

    def _create_refresh_token_str(self, jti=None, family=None, env="test", include_family=True):
        from rest_framework_simplejwt.tokens import RefreshToken
        token = RefreshToken()
        token["user_id"] = str(uuid.uuid4())
        token["jti"] = jti or str(uuid.uuid4())
        if include_family:
            token["family"] = family or str(uuid.uuid4())
        token["env"] = env
        return str(token)

    def test_reused_token_blacklists_family(self, handler, blacklist, settings):
        settings.SECRET_KEY = TEST_SECRET
        settings.SIMPLE_JWT = {"SIGNING_KEY": TEST_SECRET, "ALGORITHM": "HS256"}

        family = str(uuid.uuid4())
        blacklist.is_blacklisted.return_value = True

        with pytest.raises(ValueError, match="revoked"):
            handler.refresh_access_token(self._create_refresh_token_str(family=family))

        blacklist.blacklist_family.assert_called_once_with(family)

    def test_reused_token_rejects_missing_family(self, handler, blacklist, settings):
        settings.SECRET_KEY = TEST_SECRET
        settings.SIMPLE_JWT = {"SIGNING_KEY": TEST_SECRET, "ALGORITHM": "HS256"}

        blacklist.is_blacklisted.return_value = True
        with pytest.raises(ValueError, match="family"):
            handler.refresh_access_token(self._create_refresh_token_str(include_family=False))

        blacklist.blacklist_family.assert_not_called()

    def test_valid_token_not_blacklisted(self, handler, blacklist, settings):
        settings.SECRET_KEY = TEST_SECRET
        settings.SIMPLE_JWT = {"SIGNING_KEY": TEST_SECRET, "ALGORITHM": "HS256"}

        blacklist.is_blacklisted.return_value = False
        handler.refresh_access_token(self._create_refresh_token_str())
        blacklist.blacklist_family.assert_not_called()
