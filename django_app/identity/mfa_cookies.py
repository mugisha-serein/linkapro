from __future__ import annotations

from django.conf import settings
from django.core.exceptions import ImproperlyConfigured
from django_app.identity.cookies import _cookie_domain, _cookie_samesite, _cookie_secure

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
        secure=_cookie_secure("MFA_TEMP_TOKEN_COOKIE"),
        samesite=_cookie_samesite("MFA_TEMP_TOKEN_COOKIE"),
        path="/",
        domain=_cookie_domain("MFA_TEMP_TOKEN_COOKIE"),
    )


def clear_mfa_temp_cookie(response) -> None:
    response.set_cookie(
        get_mfa_temp_cookie_name(),
        "",
        max_age=0,
        expires="Thu, 01 Jan 1970 00:00:00 GMT",
        httponly=True,
        secure=_cookie_secure("MFA_TEMP_TOKEN_COOKIE"),
        samesite=_cookie_samesite("MFA_TEMP_TOKEN_COOKIE"),
        path="/",
        domain=_cookie_domain("MFA_TEMP_TOKEN_COOKIE"),
    )
