import hashlib
import hmac
import secrets
import time
import json
import logging
from typing import Optional
from django.http import HttpResponse, JsonResponse
from django.conf import settings
from django.core.cache import cache
from redis import Redis

from payments.application.ports import IApiKeyRepository
from payments.infrastructure.repositories import DjangoApiKeyRepository

logger = logging.getLogger(__name__)


class HmacRequestValidator:
    def __init__(self, get_response):
        self.get_response = get_response
        self.redis_client = Redis.from_url(settings.REDIS_URL)
        self.api_key_repo = DjangoApiKeyRepository()
        self.max_time_diff = 300  # 5 minutes
        self.nonce_ttl = 900      # 15 minutes
        self.max_failures = 10
        self.failure_window = 300  # 5 minutes

    def __call__(self, request):
        # Only apply to /payments/ endpoints
        if not request.path.startswith("/api/django/payments/"):
            return self.get_response(request)

        # Skip if not a protected method (e.g., GET status may be public? We require auth for all)
        # Webhook endpoint uses different auth; skip HMAC for webhook
        if request.path.endswith("/webhooks/flutterwave/") or \
           "/.well-known/payment-public-key" in request.path:
            return self.get_response(request)

        # Dashboard/browser payment requests are protected by JWT auth in DRF.
        # HMAC is reserved for external API-key integrations; requiring it here
        # makes normal authenticated frontend requests fail before they reach DRF.
        authorization = request.headers.get("Authorization", "")
        if authorization.startswith("Bearer "):
            return self.get_response(request)

        # Validate request
        error_response = self._validate_request(request)
        if error_response:
            return error_response

        return self.get_response(request)

    def _validate_request(self, request) -> Optional[HttpResponse]:
        # Extract headers
        timestamp_str = request.headers.get("X-Timestamp")
        nonce = request.headers.get("X-Nonce")
        signature = request.headers.get("X-Signature")
        key_id = request.headers.get("X-Key-ID")

        if not all([timestamp_str, nonce, signature, key_id]):
            return JsonResponse({"error": "Missing required headers"}, status=401)

        # Validate timestamp
        try:
            timestamp = int(timestamp_str)
        except ValueError:
            return JsonResponse({"error": "Invalid timestamp"}, status=401)

        now = int(time.time())
        if abs(now - timestamp) > self.max_time_diff:
            return JsonResponse({"error": "Request expired"}, status=401)

        # Replay protection
        nonce_key = f"nonce:{nonce}"
        if self.redis_client.exists(nonce_key):
            self._record_failure(request)
            return JsonResponse({"error": "Nonce already used"}, status=401)

        # Fetch API key
        key_data = self.api_key_repo.find_by_key_id(key_id)
        if not key_data:
            self._record_failure(request)
            return JsonResponse({"error": "Invalid API key"}, status=401)

        # Check scopes based on endpoint
        required_scope = self._get_required_scope(request)
        if required_scope not in key_data["scopes"] and "full_access" not in key_data["scopes"]:
            self._record_failure(request)
            return JsonResponse({"error": "Insufficient scope"}, status=403)

        # Reconstruct canonical string
        canonical = self._build_canonical(request, timestamp_str, nonce)

        # Verify HMAC
        secret = key_data.get("secret")
        if not secret:
            self._record_failure(request)
            return JsonResponse({"error": "Invalid API key"}, status=401)

        expected_signature = hmac.new(
            secret.encode(),
            canonical.encode(),
            hashlib.sha256
        ).hexdigest()

        if not secrets.compare_digest(expected_signature, signature):
            self._record_failure(request)
            return JsonResponse({"error": "Invalid signature"}, status=401)

        # Success: store nonce and mark key used
        self.redis_client.setex(nonce_key, self.nonce_ttl, "1")
        self.api_key_repo.mark_used(key_id)
        # Store user_id in request for downstream use
        request.api_user_id = key_data["user_id"]
        return None

    def _build_canonical(self, request, timestamp: str, nonce: str) -> str:
        body = request.body.decode('utf-8') if request.body else ""
        body_hash = hashlib.sha256(body.encode()).hexdigest()
        return f"{request.method}\n{request.path}\n{timestamp}\n{nonce}\n{body_hash}"

    def _get_required_scope(self, request) -> str:
        if request.path.endswith("/initiate/"):
            return "initiate_payment"
        elif "/status/" in request.path:
            return "read_status"
        return "full_access"  # default for other endpoints

    def _record_failure(self, request) -> None:
        ip = self._get_client_ip(request)
        key = f"hmac_failures:{ip}"
        current = cache.get(key, 0)
        cache.set(key, current + 1, timeout=self.failure_window)
        if current + 1 >= self.max_failures:
            # Emit SecurityEvent (simplified: log critical)
            logger.critical("HMAC_FAILURE_BLOCK", extra={"ip": ip})
            # Could also add to Redis blocklist
            self.redis_client.setex(f"blocked_ip:{ip}", 3600, "1")

    def _get_client_ip(self, request) -> str:
        x_forwarded_for = request.META.get('HTTP_X_FORWARDED_FOR')
        if x_forwarded_for:
            ip = x_forwarded_for.split(',')[0].strip()
        else:
            ip = request.META.get('REMOTE_ADDR')
        return ip
