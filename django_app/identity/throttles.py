import hashlib
import hmac
import logging
import math
import time

from django.conf import settings
from django.core.cache import cache
from rest_framework.exceptions import APIException
from rest_framework.settings import api_settings
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


class AuthRateLimited(APIException):
    status_code = 429
    default_code = "login_rate_limited"

    def __init__(self, wait=None, request=None):
        self.wait = math.ceil(wait) if wait else None
        super().__init__("Too many sign-in attempts. Please try again later.")
        self.detail = api_error_payload(
            code=self.default_code,
            message="Too many sign-in attempts. Please try again later.",
            request=request,
        )


class RegistrationRateLimited(APIException):
    status_code = 429
    default_code = "registration_rate_limited"

    def __init__(self, wait=None, request=None):
        self.wait = math.ceil(wait) if wait else None
        super().__init__("Too many account creation attempts. Please try again later.")
        self.detail = api_error_payload(
            code=self.default_code,
            message="Too many account creation attempts. Please try again later.",
            request=request,
        )


class TwoFactorRateLimited(APIException):
    status_code = 429
    default_code = "mfa_rate_limited"

    def __init__(self, wait=None, request=None):
        self.wait = math.ceil(wait) if wait else None
        super().__init__("Too many verification attempts. Please try again later.")
        self.detail = api_error_payload(
            code=self.default_code,
            message="Too many verification attempts. Please try again later.",
            request=request,
        )


class PasswordRecoveryThrottle(SimpleRateThrottle):
    cache = cache

    def get_rate(self):
        return api_settings.DEFAULT_THROTTLE_RATES.get(self.scope)

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


class AuthEndpointThrottle(PasswordRecoveryThrottle):
    def _log_limited(self, request, *, reason: str) -> None:
        event_name = _rate_limited_event(self.scope)
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


class LoginIPThrottle(AuthEndpointThrottle):
    scope = "login_ip"

    def get_cache_key(self, request, view):
        return self._cache_key(rate_limit_hash(get_client_ip(request)))

    def get_safe_metadata(self, request) -> dict:
        return {"client_ip_hash": rate_limit_hash(get_client_ip(request))}


class LoginEmailThrottle(AuthEndpointThrottle):
    scope = "login_email"

    def get_cache_key(self, request, view):
        return self._cache_key(rate_limit_hash(_normalized_email(request)))

    def get_safe_metadata(self, request) -> dict:
        email = _normalized_email(request)
        return {
            "email_hash": rate_limit_hash(email),
            "email_domain": _email_domain(email),
        }


class LoginUserThrottle(LoginEmailThrottle):
    scope = "login_user"


class RegisterIPThrottle(AuthEndpointThrottle):
    scope = "register_ip"

    def get_cache_key(self, request, view):
        return self._cache_key(rate_limit_hash(get_client_ip(request)))

    def get_safe_metadata(self, request) -> dict:
        return {"client_ip_hash": rate_limit_hash(get_client_ip(request))}


class RegisterEmailDomainThrottle(AuthEndpointThrottle):
    scope = "register_email_domain"

    def get_cache_key(self, request, view):
        return self._cache_key(rate_limit_hash(_email_domain(_normalized_email(request))))

    def get_safe_metadata(self, request) -> dict:
        email = _normalized_email(request)
        return {
            "email_domain_hash": rate_limit_hash(_email_domain(email)),
            "email_domain": _email_domain(email),
        }


class TwoFactorIPThrottle(AuthEndpointThrottle):
    scope = "two_factor_ip"

    def get_cache_key(self, request, view):
        return self._cache_key(rate_limit_hash(get_client_ip(request)))

    def get_safe_metadata(self, request) -> dict:
        return {"client_ip_hash": rate_limit_hash(get_client_ip(request))}


class TwoFactorTempTokenThrottle(AuthEndpointThrottle):
    scope = "two_factor_temp_token"

    def get_cache_key(self, request, view):
        return self._cache_key(rate_limit_hash(_temp_token(request)))

    def get_safe_metadata(self, request) -> dict:
        return {"temp_token_hash": rate_limit_hash(_temp_token(request))}


def is_login_locked_out(request, email: str | None = None) -> bool:
    email_hash = rate_limit_hash(_normalize_email_value(email) or _normalized_email(request))
    ip_hash = rate_limit_hash(get_client_ip(request))
    return _any_lockout_active(
        ("login_lock", email_hash),
        ("login_lock_ip", ip_hash),
        request=request,
        event="login_rate_limited",
        metadata={"email_hash": email_hash, "client_ip_hash": ip_hash},
    )


def record_login_failure(request, email: str | None = None, *, auth_status=None) -> None:
    email_hash = rate_limit_hash(_normalize_email_value(email) or _normalized_email(request))
    ip_hash = rate_limit_hash(get_client_ip(request))
    threshold = int(getattr(settings, "LOGIN_FAILURE_LOCKOUT_THRESHOLD", 8))
    ttl = int(getattr(settings, "LOGIN_FAILURE_LOCKOUT_SECONDS", 900))
    metadata = {
        "email_hash": email_hash,
        "client_ip_hash": ip_hash,
        "auth_status": getattr(auth_status, "value", str(auth_status)) if auth_status is not None else None,
    }
    logger.info(
        "login_failed",
        extra={
            "endpoint": request.path,
            "request_id": getattr(request, "correlation_id", None),
            **metadata,
        },
    )
    _increment_failure_counter("login_fail", "login_lock", email_hash, threshold, ttl, request, metadata)
    _increment_failure_counter("login_fail_ip", "login_lock_ip", ip_hash, threshold, ttl, request, metadata)


def clear_login_failures(request, email: str | None = None, *, user_id=None) -> None:
    email_hash = rate_limit_hash(_normalize_email_value(email) or _normalized_email(request))
    ip_hash = rate_limit_hash(get_client_ip(request))
    _safe_cache_delete_many(
        [
            _state_key("login_fail", email_hash),
            _state_key("login_lock", email_hash),
            _state_key("login_fail_ip", ip_hash),
            _state_key("login_lock_ip", ip_hash),
        ],
        request=request,
        event="login_failure_state_clear_failed",
    )
    logger.info(
        "login_success",
        extra={
            "endpoint": request.path,
            "request_id": getattr(request, "correlation_id", None),
            "email_hash": email_hash,
            "client_ip_hash": ip_hash,
            "user_id": str(user_id) if user_id else None,
        },
    )


def is_mfa_locked_out(request, temp_token: str | None = None) -> bool:
    token_hash = rate_limit_hash(_normalize_token_value(temp_token) or _temp_token(request))
    ip_hash = rate_limit_hash(get_client_ip(request))
    return _any_lockout_active(
        ("mfa_lock", token_hash),
        ("mfa_lock_ip", ip_hash),
        request=request,
        event="mfa_rate_limited",
        metadata={"temp_token_hash": token_hash, "client_ip_hash": ip_hash},
    )


def record_mfa_failure(request, temp_token: str | None = None, *, auth_status=None) -> None:
    token_hash = rate_limit_hash(_normalize_token_value(temp_token) or _temp_token(request))
    ip_hash = rate_limit_hash(get_client_ip(request))
    threshold = int(getattr(settings, "MFA_FAILURE_LOCKOUT_THRESHOLD", 5))
    ttl = int(getattr(settings, "MFA_FAILURE_LOCKOUT_SECONDS", 900))
    metadata = {
        "temp_token_hash": token_hash,
        "client_ip_hash": ip_hash,
        "auth_status": getattr(auth_status, "value", str(auth_status)) if auth_status is not None else None,
    }
    logger.info(
        "mfa_failed",
        extra={
            "endpoint": request.path,
            "request_id": getattr(request, "correlation_id", None),
            **metadata,
        },
    )
    _increment_failure_counter("mfa_fail", "mfa_lock", token_hash, threshold, ttl, request, metadata)
    _increment_failure_counter("mfa_fail_ip", "mfa_lock_ip", ip_hash, threshold, ttl, request, metadata)


def clear_mfa_failures(request, temp_token: str | None = None, *, user_id=None) -> None:
    token_hash = rate_limit_hash(_normalize_token_value(temp_token) or _temp_token(request))
    ip_hash = rate_limit_hash(get_client_ip(request))
    _safe_cache_delete_many(
        [
            _state_key("mfa_fail", token_hash),
            _state_key("mfa_lock", token_hash),
            _state_key("mfa_fail_ip", ip_hash),
            _state_key("mfa_lock_ip", ip_hash),
        ],
        request=request,
        event="mfa_failure_state_clear_failed",
    )
    logger.info(
        "mfa_success",
        extra={
            "endpoint": request.path,
            "request_id": getattr(request, "correlation_id", None),
            "temp_token_hash": token_hash,
            "client_ip_hash": ip_hash,
            "user_id": str(user_id) if user_id else None,
        },
    )


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


def _temp_token(request) -> str:
    return str(request.data.get("temp_token", "") or "").strip()


def _normalize_email_value(email: str | None) -> str:
    return str(email or "").strip().lower()


def _normalize_token_value(token: str | None) -> str:
    return str(token or "").strip()


def _email_domain(email: str) -> str:
    return email.rsplit("@", 1)[1] if "@" in email else ""


def _rate_limited_event(scope: str) -> str:
    if scope.startswith("register"):
        return "registration_rate_limited"
    if scope.startswith("two_factor"):
        return "mfa_rate_limited"
    return "login_rate_limited"


def _state_key(prefix: str, fingerprint: str | None) -> str | None:
    if not fingerprint:
        return None
    return f"{prefix}:{fingerprint}"


def _any_lockout_active(*entries, request, event: str, metadata: dict) -> bool:
    try:
        for prefix, fingerprint in entries:
            key = _state_key(prefix, fingerprint)
            if key and cache.get(key):
                logger.warning(
                    event,
                    extra={
                        "endpoint": request.path,
                        "request_id": getattr(request, "correlation_id", None),
                        "reason": "progressive_lockout",
                        **metadata,
                    },
                )
                return True
    except Exception as exc:
        logger.error(
            "rate_limiter_unavailable",
            extra={
                "endpoint": request.path,
                "request_id": getattr(request, "correlation_id", None),
                "reason": exc.__class__.__name__,
                **metadata,
            },
            exc_info=True,
        )
        logger.warning(
            event,
            extra={
                "endpoint": request.path,
                "request_id": getattr(request, "correlation_id", None),
                "reason": "rate_limiter_unavailable",
                **metadata,
            },
        )
        return True
    return False


def _increment_failure_counter(
    counter_prefix: str,
    lock_prefix: str,
    fingerprint: str | None,
    threshold: int,
    ttl: int,
    request,
    metadata: dict,
) -> None:
    counter_key = _state_key(counter_prefix, fingerprint)
    lock_key = _state_key(lock_prefix, fingerprint)
    if not counter_key or not lock_key:
        return

    try:
        added = cache.add(counter_key, 1, timeout=ttl)
        count = 1 if added else cache.incr(counter_key)
        if count >= threshold:
            cache.set(lock_key, "1", timeout=ttl)
            logger.warning(
                "auth_lockout_triggered",
                extra={
                    "endpoint": request.path,
                    "request_id": getattr(request, "correlation_id", None),
                    "counter": counter_prefix,
                    "threshold": threshold,
                    **metadata,
                },
            )
    except Exception as exc:
        logger.error(
            "rate_limiter_unavailable",
            extra={
                "endpoint": request.path,
                "request_id": getattr(request, "correlation_id", None),
                "counter": counter_prefix,
                "reason": exc.__class__.__name__,
                **metadata,
            },
            exc_info=True,
        )


def _safe_cache_delete_many(keys, *, request, event: str) -> None:
    safe_keys = [key for key in keys if key]
    if not safe_keys:
        return
    try:
        cache.delete_many(safe_keys)
    except Exception as exc:
        logger.error(
            event,
            extra={
                "endpoint": request.path,
                "request_id": getattr(request, "correlation_id", None),
                "reason": exc.__class__.__name__,
            },
            exc_info=True,
        )
