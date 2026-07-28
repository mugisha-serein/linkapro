"""Django wiring for application-layer OAuth state helpers."""

from django.conf import settings
from django.core.cache import cache
from django.core.exceptions import ImproperlyConfigured

from application.identity.shared.oauth_state import (
    ALLOWED_OAUTH_SIGNUP_ROLES,
    OAUTH_STATE_COOKIE_NAME,
    OAuthStateChallenge,
    OAuthStateResult,
    clear_oauth_state_cookie as clear_oauth_state_cookie_base,
    consume_oauth_state as consume_oauth_state_base,
    issue_oauth_state as issue_oauth_state_base,
    set_oauth_state_cookie as set_oauth_state_cookie_base,
)


def _signing_key() -> str:
    return str(settings.SECRET_KEY)


def issue_oauth_state(signup_role: str) -> OAuthStateChallenge:
    return issue_oauth_state_base(
        signup_role,
        signing_key=_signing_key(),
        state_cache=cache,
    )


def consume_oauth_state(state: str | None, cookie_nonce: str | None) -> OAuthStateResult | None:
    return consume_oauth_state_base(
        state,
        cookie_nonce,
        signing_key=_signing_key(),
        state_cache=cache,
    )


def set_oauth_state_cookie(response, challenge: OAuthStateChallenge) -> None:
    set_oauth_state_cookie_base(
        response,
        challenge,
        secure=_oauth_state_cookie_secure(),
        samesite=_oauth_state_cookie_samesite(),
        path=_oauth_state_cookie_path(),
        domain=_oauth_state_cookie_domain(),
    )


def clear_oauth_state_cookie(response) -> None:
    clear_oauth_state_cookie_base(
        response,
        secure=_oauth_state_cookie_secure(),
        samesite=_oauth_state_cookie_samesite(),
        path=_oauth_state_cookie_path(),
        domain=_oauth_state_cookie_domain(),
    )


def _oauth_state_cookie_domain() -> str | None:
    cookie_domain = str(getattr(settings, "OAUTH_STATE_COOKIE_DOMAIN", "") or "").strip()
    return cookie_domain or None


def _oauth_state_cookie_path() -> str:
    return str(getattr(settings, "OAUTH_STATE_COOKIE_PATH", "/") or "/").strip() or "/"


def _oauth_state_cookie_samesite() -> str:
    configured = str(getattr(settings, "OAUTH_STATE_COOKIE_SAMESITE", "") or "").strip()
    if configured:
        normalized = configured.capitalize()
        if normalized not in {"Lax", "Strict", "None"}:
            raise ImproperlyConfigured("OAUTH_STATE_COOKIE_SAMESITE must be one of Lax, Strict, or None")
        return normalized
    return "Lax"


def _oauth_state_cookie_secure() -> bool:
    configured = getattr(settings, "OAUTH_STATE_COOKIE_SECURE", None)
    secure = not settings.DEBUG if configured is None else bool(configured)
    if not settings.DEBUG and not secure:
        raise ImproperlyConfigured("OAUTH_STATE_COOKIE_SECURE must be enabled in production")
    if _oauth_state_cookie_samesite() == "None" and not secure:
        raise ImproperlyConfigured("SameSite=None OAuth state cookies require Secure=True")
    return secure


__all__ = [
    "ALLOWED_OAUTH_SIGNUP_ROLES",
    "OAUTH_STATE_COOKIE_NAME",
    "OAuthStateChallenge",
    "OAuthStateResult",
    "clear_oauth_state_cookie",
    "consume_oauth_state",
    "issue_oauth_state",
    "set_oauth_state_cookie",
]
