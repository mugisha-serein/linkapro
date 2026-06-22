import hashlib
import hmac
import logging
import math
import time

from django.conf import settings
from django.core.cache import cache
from rest_framework.exceptions import APIException
from rest_framework.throttling import SimpleRateThrottle

from django_app.common.api_responses import api_error_payload

logger = logging.getLogger(__name__)


class PasswordRecoveryRateLimited(APIException):
    status_code = 429
    default_code = "password_recovery_rate_limited"

    def __init__(self, wait=None):
        self.wait = math.ceil(wait) if wait else None
        super().__init__("Too many password reset attempts. Please try again later.")
        self.detail = api_error_payload(
            code=self.default_code,
            message="Too many password reset attempts. Please try again later.",
        )


class PasswordResetRateLimited(APIException):
    status_code = 429
    default_code = "password_reset_rate_limited"

    def __init__(self, wait=None):
        self.wait = math.ceil(wait) if wait else None
        super().__init__("Too many reset attempts. Please wait before trying again.")
        self.detail = api_error_payload(
            code=self.default_code,
            message="Too many reset attempts. Please wait before trying again.",
        )


class PasswordRecoveryThrottle(SimpleRateThrottle):
    cache = cache

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
            "password_recovery_rate_limit_checked",
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

    def _log_limited(self, request, *, reason: str) -> None:
        event_name = "forgot_password_rate_limited" if self.scope.startswith("forgot_password") else "reset_password_rate_limited"
        logger.warning(
            event_name,
            extra={
                "endpoint": request.path,
                "scope": self.scope,
                "request_id": getattr(request, "correlation_id", None),
                "reason": reason,
                **self.safe_metadata,
            },
        )

    def get_safe_metadata(self, request) -> dict:
        return {}

    def _cache_key(self, fingerprint: str | None):
        if not fingerprint:
            return None
        return self.cache_format % {"scope": self.scope, "ident": fingerprint}


class ForgotPasswordIPThrottle(PasswordRecoveryThrottle):
    scope = "forgot_password_ip"

    def get_cache_key(self, request, view):
        return self._cache_key(rate_limit_hash(get_client_ip(request)))

    def get_safe_metadata(self, request) -> dict:
        return {"client_ip_hash": rate_limit_hash(get_client_ip(request))}


class ForgotPasswordEmailThrottle(PasswordRecoveryThrottle):
    scope = "forgot_password_email"

    def get_cache_key(self, request, view):
        return self._cache_key(rate_limit_hash(_normalized_email(request)))

    def get_safe_metadata(self, request) -> dict:
        email = _normalized_email(request)
        return {
            "email_hash": rate_limit_hash(email),
            "email_domain": email.rsplit("@", 1)[1] if "@" in email else "",
        }


class ResetPasswordIPThrottle(PasswordRecoveryThrottle):
    scope = "reset_password_ip"

    def get_cache_key(self, request, view):
        return self._cache_key(rate_limit_hash(get_client_ip(request)))

    def get_safe_metadata(self, request) -> dict:
        return {"client_ip_hash": rate_limit_hash(get_client_ip(request))}


class ResetPasswordTokenThrottle(PasswordRecoveryThrottle):
    scope = "reset_password_token"

    def get_cache_key(self, request, view):
        return self._cache_key(rate_limit_hash(_reset_token(request)))

    def get_safe_metadata(self, request) -> dict:
        return {"token_hash": rate_limit_hash(_reset_token(request))}


def get_client_ip(request) -> str:
    if getattr(settings, "PASSWORD_RECOVERY_TRUST_X_FORWARDED_FOR", False):
        forwarded_for = request.META.get("HTTP_X_FORWARDED_FOR", "")
        if forwarded_for:
            return forwarded_for.split(",", 1)[0].strip()
    return request.META.get("REMOTE_ADDR", "") or "unknown"


def rate_limit_hash(value: str | None) -> str | None:
    if not value:
        return None
    key = str(getattr(settings, "RATE_LIMIT_HASH_KEY", "") or settings.SECRET_KEY).encode("utf-8")
    return hmac.new(key, value.encode("utf-8"), hashlib.sha256).hexdigest()


def _normalized_email(request) -> str:
    return str(request.data.get("email", "") or "").strip().lower()


def _reset_token(request) -> str:
    return str(request.data.get("token", "") or "").strip()
