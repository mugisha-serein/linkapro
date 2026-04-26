import hashlib
import hmac
import time
import uuid
import json
import pytest
from unittest.mock import MagicMock, patch
from django.test import RequestFactory

from payments.infrastructure.middleware import HmacRequestValidator


class TestHmacMiddlewareUnit:
    """Unit tests for HmacRequestValidator._validate_request()."""

    @pytest.fixture
    def factory(self):
        return RequestFactory()

    @pytest.fixture
    def mock_redis_client(self):
        client = MagicMock()
        client.exists.return_value = False   # default: nonce not seen
        return client

    @pytest.fixture
    def mock_repo(self):
        repo = MagicMock()
        repo.find_by_key_id.return_value = {
            "secret": "super_secret_key",            # plaintext secret for HMAC
            "scopes": ["initiate_payment"],
            "user_id": "user123",
            "is_active": True,
            "expires_at": None,
        }
        return repo

    @pytest.fixture
    def middleware(self, mock_redis_client, mock_repo):
        # Create instance, but we will patch the dependencies used in __call__
        with patch("payments.infrastructure.middleware.Redis.from_url", return_value=mock_redis_client):
            with patch("payments.infrastructure.middleware.DjangoApiKeyRepository") as RepoClass:
                RepoClass.return_value = mock_repo
                validator = HmacRequestValidator(lambda r: None)
        # Override just in case, but the patches above should cover __init__ and __call__
        validator.redis_client = mock_redis_client
        validator.api_key_repo = mock_repo
        return validator

    def _sign_request(self, method, path, body_bytes, secret, key_id, timestamp=None, nonce=None):
        timestamp = timestamp or str(int(time.time()))
        nonce = nonce or str(uuid.uuid4())
        body_hash = hashlib.sha256(body_bytes).hexdigest()
        canonical = f"{method}\n{path}\n{timestamp}\n{nonce}\n{body_hash}"
        signature = hmac.new(secret.encode(), canonical.encode(), hashlib.sha256).hexdigest()
        headers = {
            "HTTP_X_TIMESTAMP": timestamp,
            "HTTP_X_NONCE": nonce,
            "HTTP_X_SIGNATURE": signature,
            "HTTP_X_KEY_ID": key_id,
        }
        return headers, body_bytes

    def test_valid_signature_passes(self, factory, middleware, mock_redis_client):
        url = "/api/django/payments/initiate/"
        secret = "super_secret_key"
        key_id = "pk_test123"
        body = json.dumps({"amount": "1000"}).encode()
        headers, body_bytes = self._sign_request("POST", url, body, secret, key_id)

        request = factory.post(url, data=body_bytes, content_type="application/json", **headers)
        result = middleware._validate_request(request)
        assert result is None, f"Expected None, got {result.status_code} {result.content}"

    def test_expired_timestamp(self, factory, middleware, mock_redis_client):
        url = "/api/django/payments/initiate/"
        secret = "super_secret_key"
        key_id = "pk_test123"
        timestamp = str(int(time.time()) - 400)
        headers, body_bytes = self._sign_request("POST", url, b"{}", secret, key_id, timestamp=timestamp)
        request = factory.post(url, data=body_bytes, content_type="application/json", **headers)
        result = middleware._validate_request(request)
        assert result.status_code == 401
        data = json.loads(result.content)
        assert "expired" in data["error"].lower()

    def test_replay_nonce(self, factory, middleware, mock_redis_client):
        url = "/api/django/payments/initiate/"
        secret = "super_secret_key"
        key_id = "pk_test123"
        nonce = str(uuid.uuid4())
        headers, body_bytes = self._sign_request("POST", url, b"{}", secret, key_id, nonce=nonce)

        # First request – nonce not exists
        mock_redis_client.exists.return_value = False
        request = factory.post(url, data=body_bytes, content_type="application/json", **headers)
        assert middleware._validate_request(request) is None

        # Second request – nonce already used
        mock_redis_client.exists.return_value = True
        request = factory.post(url, data=body_bytes, content_type="application/json", **headers)
        result = middleware._validate_request(request)
        assert result.status_code == 401
        data = json.loads(result.content)
        assert "nonce" in data["error"].lower()

    def test_invalid_signature(self, factory, middleware, mock_redis_client):
        url = "/api/django/payments/initiate/"
        secret = "super_secret_key"
        key_id = "pk_test123"
        headers, body_bytes = self._sign_request("POST", url, b"{}", secret, key_id)
        headers["HTTP_X_SIGNATURE"] = "invalidsignature"
        request = factory.post(url, data=body_bytes, content_type="application/json", **headers)
        result = middleware._validate_request(request)
        assert result.status_code == 401
        data = json.loads(result.content)
        assert "signature" in data["error"].lower()

    def test_insufficient_scope(self, factory, middleware, mock_repo, mock_redis_client):
        # Change scopes returned by repo
        mock_repo.find_by_key_id.return_value["scopes"] = ["read_status"]
        url = "/api/django/payments/initiate/"
        secret = "super_secret_key"
        key_id = "pk_test123"
        headers, body_bytes = self._sign_request("POST", url, b"{}", secret, key_id)
        request = factory.post(url, data=body_bytes, content_type="application/json", **headers)
        result = middleware._validate_request(request)
        assert result.status_code == 403
        data = json.loads(result.content)
        assert "scope" in data["error"].lower()

    def test_missing_headers(self, factory, middleware):
        request = factory.post("/api/django/payments/initiate/")
        result = middleware._validate_request(request)
        assert result.status_code == 401
        data = json.loads(result.content)
        assert "missing" in data["error"].lower()