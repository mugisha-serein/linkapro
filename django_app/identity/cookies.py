from django.conf import settings
from django.core.exceptions import ImproperlyConfigured


DEFAULT_REFRESH_COOKIE_NAME = "refresh_token"
LEGACY_REFRESH_COOKIE_NAMES = ("access_token",)


def _refresh_cookie_name() -> str:
    cookie_name = str(getattr(settings, "REFRESH_TOKEN_COOKIE_NAME", DEFAULT_REFRESH_COOKIE_NAME) or "").strip()
    if not cookie_name:
        raise ImproperlyConfigured("REFRESH_TOKEN_COOKIE_NAME must not be empty")
    return cookie_name


def _refresh_cookie_domain() -> str | None:
    cookie_domain = str(getattr(settings, "REFRESH_TOKEN_COOKIE_DOMAIN", "") or "").strip()
    return cookie_domain or None


def _refresh_cookie_samesite() -> str:
    configured = str(getattr(settings, "REFRESH_TOKEN_COOKIE_SAMESITE", "") or "").strip()
    if configured:
        normalized = configured.capitalize()
        if normalized not in {"Lax", "Strict", "None"}:
            raise ImproperlyConfigured("REFRESH_TOKEN_COOKIE_SAMESITE must be one of Lax, Strict, or None")
        return normalized
    return "None" if not settings.DEBUG else "Lax"


def _refresh_cookie_secure() -> bool:
    configured = getattr(settings, "REFRESH_TOKEN_COOKIE_SECURE", None)
    secure = not settings.DEBUG if configured is None else bool(configured)
    if not settings.DEBUG and not secure:
        raise ImproperlyConfigured("REFRESH_TOKEN_COOKIE_SECURE must be enabled in production")
    if _refresh_cookie_samesite() == "None" and not secure:
        raise ImproperlyConfigured("SameSite=None refresh cookies require Secure=True")
    return secure


def _refresh_cookie_max_age() -> int:
    return int(settings.SIMPLE_JWT["REFRESH_TOKEN_LIFETIME"].total_seconds())


def set_refresh_cookie(response, refresh_token: str) -> None:
    response.set_cookie(
        _refresh_cookie_name(),
        refresh_token,
        max_age=_refresh_cookie_max_age(),
        httponly=True,
        secure=_refresh_cookie_secure(),
        samesite=_refresh_cookie_samesite(),
        path="/",
        domain=_refresh_cookie_domain(),
    )


def clear_auth_cookies(response) -> None:
    cookie_domain = _refresh_cookie_domain()
    cookie_secure = _refresh_cookie_secure()
    cookie_samesite = _refresh_cookie_samesite()

    for cookie_name in (*LEGACY_REFRESH_COOKIE_NAMES, _refresh_cookie_name()):
        response.set_cookie(
            cookie_name,
            "",
            max_age=0,
            expires="Thu, 01 Jan 1970 00:00:00 GMT",
            httponly=True,
            secure=cookie_secure,
            samesite=cookie_samesite,
            path="/",
            domain=cookie_domain,
        )
