from django.conf import settings
from django.core.exceptions import ImproperlyConfigured


DEFAULT_REFRESH_COOKIE_NAME = "refresh_token"
LEGACY_REFRESH_COOKIE_NAMES = ("access_token",)


def get_refresh_cookie_name() -> str:
    cookie_name = str(getattr(settings, "REFRESH_TOKEN_COOKIE_NAME", DEFAULT_REFRESH_COOKIE_NAME) or "").strip()
    if not cookie_name:
        raise ImproperlyConfigured("REFRESH_TOKEN_COOKIE_NAME must not be empty")
    return cookie_name


def extract_refresh_token(request) -> str | None:
    token = request.data.get("refresh") or request.COOKIES.get(get_refresh_cookie_name())
    return str(token).strip() if token else None


def _cookie_domain(setting_prefix: str) -> str | None:
    cookie_domain = str(getattr(settings, f"{setting_prefix}_DOMAIN", "") or "").strip()
    return cookie_domain or None


def _cookie_samesite(setting_prefix: str) -> str:
    configured = str(getattr(settings, f"{setting_prefix}_SAMESITE", "") or "").strip()
    if configured:
        normalized = configured.capitalize()
        if normalized not in {"Lax", "Strict", "None"}:
            raise ImproperlyConfigured(f"{setting_prefix}_SAMESITE must be one of Lax, Strict, or None")
        return normalized
    return "None" if not settings.DEBUG else "Lax"


def _cookie_secure(setting_prefix: str) -> bool:
    configured = getattr(settings, f"{setting_prefix}_SECURE", None)
    secure = not settings.DEBUG if configured is None else bool(configured)
    if not settings.DEBUG and not secure:
        raise ImproperlyConfigured(f"{setting_prefix}_SECURE must be enabled in production")
    if _cookie_samesite(setting_prefix) == "None" and not secure:
        raise ImproperlyConfigured(f"SameSite=None {setting_prefix} cookies require Secure=True")
    return secure


def _refresh_cookie_max_age() -> int:
    return int(settings.SIMPLE_JWT["REFRESH_TOKEN_LIFETIME"].total_seconds())


def set_refresh_cookie(response, refresh_token: str) -> None:
    response.set_cookie(
        get_refresh_cookie_name(),
        refresh_token,
        max_age=_refresh_cookie_max_age(),
        httponly=True,
        secure=_cookie_secure("REFRESH_TOKEN_COOKIE"),
        samesite=_cookie_samesite("REFRESH_TOKEN_COOKIE"),
        path="/",
        domain=_cookie_domain("REFRESH_TOKEN_COOKIE"),
    )


def clear_auth_cookies(response) -> None:
    cookie_domain = _cookie_domain("REFRESH_TOKEN_COOKIE")
    cookie_secure = _cookie_secure("REFRESH_TOKEN_COOKIE")
    cookie_samesite = _cookie_samesite("REFRESH_TOKEN_COOKIE")

    for cookie_name in (*LEGACY_REFRESH_COOKIE_NAMES, get_refresh_cookie_name()):
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
