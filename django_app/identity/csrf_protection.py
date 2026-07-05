from __future__ import annotations

import hmac
from urllib.parse import urlparse

from django.conf import settings
from django.core.exceptions import ImproperlyConfigured

CSRF_COOKIE_NAME = "identity_csrf_token"
CSRF_HEADER_NAME = "HTTP_X_CSRF_TOKEN"


def cookie_session_request_is_allowed(request) -> bool:
    origin_or_referer_allowed = _origin_or_referer_allowed(request)
    if not origin_or_referer_allowed:
        return False
    if not _csrf_double_submit_required():
        return True
    return _csrf_double_submit_valid(request)


def _origin_or_referer_allowed(request) -> bool:
    origin = request.META.get("HTTP_ORIGIN")
    if origin:
        return _origin_allowed(origin)

    referer = request.META.get("HTTP_REFERER")
    if referer:
        return _origin_allowed(_origin_from_url(referer))

    return bool(settings.DEBUG and getattr(settings, "ALLOW_MISSING_ORIGIN_IN_DEBUG", True))


def _origin_allowed(origin: str | None) -> bool:
    if not origin:
        return False
    normalized = _normalize_origin(origin)
    if not normalized:
        return False
    return normalized in _allowed_origins()


def _allowed_origins() -> set[str]:
    configured = getattr(settings, "COOKIE_AUTH_ALLOWED_ORIGINS", None)
    if configured is None:
        configured = getattr(settings, "CSRF_TRUSTED_ORIGINS", []) or []
    frontend_url = getattr(settings, "FRONTEND_URL", None)
    origins = {_normalize_origin(origin) for origin in configured if _normalize_origin(origin)}
    if frontend_url:
        frontend_origin = _normalize_origin(frontend_url)
        if frontend_origin:
            origins.add(frontend_origin)
    if not origins and not settings.DEBUG:
        raise ImproperlyConfigured(
            "COOKIE_AUTH_ALLOWED_ORIGINS or FRONTEND_URL must be configured for cookie auth in production"
        )
    return origins


def _normalize_origin(origin: str) -> str | None:
    parsed = urlparse(str(origin).strip())
    if parsed.scheme not in {"http", "https"} or not parsed.netloc:
        return None
    scheme = parsed.scheme.lower()
    netloc = parsed.netloc.lower()
    return f"{scheme}://{netloc}"


def _origin_from_url(url: str) -> str | None:
    return _normalize_origin(url)


def _csrf_double_submit_required() -> bool:
    return bool(getattr(settings, "COOKIE_AUTH_CSRF_DOUBLE_SUBMIT", False))


def _csrf_double_submit_valid(request) -> bool:
    cookie_token = str(request.COOKIES.get(CSRF_COOKIE_NAME, "") or "").strip()
    header_token = str(request.META.get(CSRF_HEADER_NAME, "") or "").strip()
    if not cookie_token or not header_token:
        return False
    return hmac.compare_digest(cookie_token, header_token)
