import hashlib
import hmac
import logging
import math
import os
import time

from django.conf import settings
from django.core.cache import cache
from rest_framework.exceptions import APIException
from rest_framework.throttling import SimpleRateThrottle

from django_app.common.api_responses import api_error_payload
from django_app.identity.throttles import get_client_ip, rate_limit_hash

logger = logging.getLogger(__name__)


class TokenRefreshRateLimited(APIException):
    status_code = 429
    default_code = "token_refresh_rate_limited"

    def __init__(self, wait=None, request=None):
        self.wait = math.ceil(wait) if wait else None
        super().__init__("Too many session refresh attempts. Please try again later.")
        self.detail = api_error_payload(
            code=self.default_code,
            message="Too many session refresh attempts. Please try again later.",
            request=request,
        )


class TokenRevokeRateLimited(APIException):
    status_code = 429
    default_code = "token_revoke_rate_limited"

    def __init__(self, wait=None, request=None):
        self.wait = math.ceil(wait) if wait else None
        super().__init__("Too many sign-out attempts. Please try again later.")
        self.detail = api_error_payload(
            code=self.default_code,
            message="Too many sign-out attempts. Please try again later.",
            request=request,
        )


class TokenEndpointThrottle(SimpleRateThrottle):
    cache = cache
    env_rate_name = ""
    default_rate = "30/min"

    def get_rate(self):
        return os.environ.get(self.env_rate_name, self.default_rate)

    def allow_request(self, request, view):
        self.safe_metadata = self.get_safe_metadata(request)
        try:
            allowed = super().allow_request(request, view)
        except Exception as exc:
            self.now = time.time()
            self.num_requests = 1
            self.duration = 60
            self.history = [self.now]
            logger.error(
                "rate_limiter_unavailable",
                extra={
                    "endpoint": request.path,
                    "scope": self.scope,
                    "request_id": getattr(request, "correlation_id", None),
                    "reason": exc.__class__.__name__,
                    **self.safe_metadata,
                },
                exc_info=True,
            )
            self._log_limited(request, reason="rate_limiter_unavailable")
            return False

        logger.info(
            "token_endpoint_rate_limit_checked",
            extra={
                "endpoint": request.path,
                "scope": self.scope,
                "request_id": getattr(request, "correlation_id", None),
                "allowed": allowed,
                **self.safe_metadata,
            },
        )
        if not allowed:
            self._log_limited(request, reason="limit_exceeded")
        return allowed

    def get_cache_key(self, request, view):
        fingerprint = self.get_fingerprint(request)
        if not fingerprint:
            return None
        return self.cache_format % {"scope": self.scope, "ident": fingerprint}

    def get_fingerprint(self, request) -> str | None:
        return None

    def get_safe_metadata(self, request) -> dict:
        return {}

    def _log_limited(self, request, *, reason: str) -> None:
        logger.warning(
            self.rate_limited_event,
            extra={
                "endpoint": request.path,
                "scope": self.scope,
                "request_id": getattr(request, "correlation_id", None),
                "reason": reason,
                **self.safe_metadata,
            },
        )


class TokenRefreshIPThrottle(TokenEndpointThrottle):
    scope = "token_refresh_ip"
    env_rate_name = "TOKEN_REFRESH_IP_RATE"
    default_rate = "30/min"
    rate_limited_event = "token_refresh_rate_limited"

    def get_fingerprint(self, request) -> str | None:
        return rate_limit_hash(get_client_ip(request))

    def get_safe_metadata(self, request) -> dict:
        return {"client_ip_hash": rate_limit_hash(get_client_ip(request))}


class TokenRefreshFingerprintThrottle(TokenEndpointThrottle):
    scope = "token_refresh_fingerprint"
    env_rate_name = "TOKEN_REFRESH_FINGERPRINT_RATE"
    default_rate = "120/hour"
    rate_limited_event = "token_refresh_rate_limited"

    def get_fingerprint(self, request) -> str | None:
        return _refresh_token_fingerprint(request)

    def get_safe_metadata(self, request) -> dict:
        return {"refresh_token_hash": _refresh_token_fingerprint(request)}


class TokenRevokeIPThrottle(TokenEndpointThrottle):
    scope = "token_revoke_ip"
    env_rate_name = "TOKEN_REVOKE_IP_RATE"
    default_rate = "20/min"
    rate_limited_event = "token_revoke_rate_limited"

    def get_fingerprint(self, request) -> str | None:
        return rate_limit_hash(get_client_ip(request))

    def get_safe_metadata(self, request) -> dict:
        return {"client_ip_hash": rate_limit_hash(get_client_ip(request))}


class TokenRevokeFingerprintThrottle(TokenEndpointThrottle):
    scope = "token_revoke_fingerprint"
    env_rate_name = "TOKEN_REVOKE_FINGERPRINT_RATE"
    default_rate = "60/hour"
    rate_limited_event = "token_revoke_rate_limited"

    def get_fingerprint(self, request) -> str | None:
        return _refresh_token_fingerprint(request)

    def get_safe_metadata(self, request) -> dict:
        return {"refresh_token_hash": _refresh_token_fingerprint(request)}


def _refresh_token_fingerprint(request) -> str | None:
    token = str(request.data.get("refresh") or request.COOKIES.get("refresh_token") or "").strip()
    if not token:
        return None
    key = str(getattr(settings, "RATE_LIMIT_HASH_KEY", "") or settings.SECRET_KEY).encode("utf-8")
    digest = hmac.new(key, token.encode("utf-8"), hashlib.sha256).hexdigest()
    return digest
