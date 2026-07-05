from __future__ import annotations

from django.conf import settings
from django.core.exceptions import ImproperlyConfigured

MFA_TEMP_TOKEN_COOKIE_NAME = "mfa_temp_token"


def get_mfa_temp_cookie_name() -> str:
    cookie_name = str(getattr(settings, "MFA_TEMP_TOKEN_COOKIE_NAME", MFA_TEMP_TOKEN_COOKIE_NAME) or "").strip()
    if not cookie_name:
        raise ImproperlyConfigured("MFA_TEMP_TOKEN_COOKIE_NAME must not be empty")
    return cookie_name


def extract_mfa_temp_token(request) -> str | None:
    token = request.data.get("temp_token") or request.COOKIES.get(get_mfa_temp_cookie_name())
    return str(token).strip() if token else None


def set_mfa_temp_cookie(response, temp_token: str) -> None:
    response.set_cookie(
        get_mfa_temp_cookie_name(),
        temp_token,
        max_age=int(getattr(settings, "MFA_TEMP_TOKEN_COOKIE_MAX_AGE", 180)),
        httponly=True,
        secure=_mfa_cookie_secure(),
        samesite=_mfa_cookie_samesite(),
        path="/",
        domain=_mfa_cookie_domain(),
    )


def clear_mfa_temp_cookie(response) -> None:
    response.set_cookie(
        get_mfa_temp_cookie_name(),
        "",
        max_age=0,
        expires="Thu, 01 Jan 1970 00:00:00 GMT",
        httponly=True,
        secure=_mfa_cookie_secure(),
        samesite=_mfa_cookie_samesite(),
        path="/",
        domain=_mfa_cookie_domain(),
    )


def _mfa_cookie_domain() -> str | None:
    cookie_domain = str(getattr(settings, "MFA_TEMP_TOKEN_COOKIE_DOMAIN", "") or "").strip()
    return cookie_domain or None


def _mfa_cookie_samesite() -> str:
    configured = str(getattr(settings, "MFA_TEMP_TOKEN_COOKIE_SAMESITE", "") or "").strip()
    if configured:
        normalized = configured.capitalize()
        if normalized not in {"Lax", "Strict", "None"}:
            raise ImproperlyConfigured("MFA_TEMP_TOKEN_COOKIE_SAMESITE must be one of Lax, Strict, or None")
        return normalized
    return "None" if not settings.DEBUG else "Lax"


def _mfa_cookie_secure() -> bool:
    configured = getattr(settings, "MFA_TEMP_TOKEN_COOKIE_SECURE", None)
    secure = not settings.DEBUG if configured is None else bool(configured)
    if not settings.DEBUG and not secure:
        raise ImproperlyConfigured("MFA_TEMP_TOKEN_COOKIE_SECURE must be enabled in production")
    if _mfa_cookie_samesite() == "None" and not secure:
        raise ImproperlyConfigured("SameSite=None MFA cookies require Secure=True")
    return secure
