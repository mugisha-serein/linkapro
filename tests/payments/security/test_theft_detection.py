import uuid
import pytest
from unittest.mock import MagicMock
from payments.application.token_handlers import TokenCommandHandlers

pytestmark = pytest.mark.django_db

# Use a key long enough to avoid InsecureKeyLengthWarning (32 bytes)
TEST_SECRET = "test-secret-key-for-jwt-32bytes!"  # 32 characters


class TestTheftDetection:
    @pytest.fixture
    def blacklist(self):
        return MagicMock()

    @pytest.fixture
    def handler(self, blacklist):
        return TokenCommandHandlers(blacklist)

    def _create_refresh_token_str(self, jti=None, family=None):
        from rest_framework_simplejwt.tokens import RefreshToken
        token = RefreshToken()
        token["user_id"] = str(uuid.uuid4())
        token["jti"] = jti or str(uuid.uuid4())
        if family is not None:
            token["family"] = family
        return str(token)

    def test_reused_token_blacklists_family(self, handler, blacklist, settings):
        settings.SECRET_KEY = TEST_SECRET
        settings.SIMPLE_JWT = {"SIGNING_KEY": TEST_SECRET, "ALGORITHM": "HS256"}

        family = str(uuid.uuid4())
        blacklist.is_blacklisted.return_value = True

        with pytest.raises(ValueError, match="revoked"):
            handler.refresh_access_token(self._create_refresh_token_str(family=family))

        blacklist.blacklist_family.assert_called_once_with(family)

    def test_reused_token_does_not_blacklist_if_no_family(self, handler, blacklist, settings):
        settings.SECRET_KEY = TEST_SECRET
        settings.SIMPLE_JWT = {"SIGNING_KEY": TEST_SECRET, "ALGORITHM": "HS256"}

        blacklist.is_blacklisted.return_value = True
        with pytest.raises(ValueError, match="revoked"):
            handler.refresh_access_token(self._create_refresh_token_str(family=None))

        blacklist.blacklist_family.assert_not_called()

    def test_valid_token_not_blacklisted(self, handler, blacklist, settings):
        settings.SECRET_KEY = TEST_SECRET
        settings.SIMPLE_JWT = {"SIGNING_KEY": TEST_SECRET, "ALGORITHM": "HS256"}

        blacklist.is_blacklisted.return_value = False
        handler.refresh_access_token(self._create_refresh_token_str())
        blacklist.blacklist_family.assert_not_called()