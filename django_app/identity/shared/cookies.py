from django.conf import settings
from django.core.exceptions import ImproperlyConfigured


DEFAULT_REFRESH_COOKIE_NAME = "refresh_token"
LEGACY_REFRESH_COOKIE_NAMES = ("access_token",)
MFA_TEMP_TOKEN_COOKIE_NAME = "mfa_temp_token"


def get_refresh_cookie_name() -> str:
    return _cookie_name("REFRESH_TOKEN_COOKIE", DEFAULT_REFRESH_COOKIE_NAME)


def get_mfa_temp_cookie_name() -> str:
    return _cookie_name("MFA_TEMP_TOKEN_COOKIE", MFA_TEMP_TOKEN_COOKIE_NAME)


def extract_refresh_token(request) -> str | None:
    token = request.data.get("refresh") or request.COOKIES.get(get_refresh_cookie_name())
    return str(token).strip() if token else None


def extract_mfa_temp_token(request) -> str | None:
    token = request.data.get("temp_token") or request.COOKIES.get(get_mfa_temp_cookie_name())
    return str(token).strip() if token else None


def _cookie_name(setting_prefix: str, default: str) -> str:
    cookie_name = str(getattr(settings, f"{setting_prefix}_NAME", default) or "").strip()
    if not cookie_name:
        raise ImproperlyConfigured(f"{setting_prefix}_NAME must not be empty")
    return cookie_name


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


def _mfa_temp_cookie_max_age() -> int:
    return int(getattr(settings, "MFA_TEMP_TOKEN_COOKIE_MAX_AGE", 180))


def _set_cookie(response, *, setting_prefix: str, name: str, value: str, max_age: int) -> None:
    response.set_cookie(
        name,
        value,
        max_age=max_age,
        httponly=True,
        secure=_cookie_secure(setting_prefix),
        samesite=_cookie_samesite(setting_prefix),
        path="/",
        domain=_cookie_domain(setting_prefix),
    )


def _clear_cookie(response, *, setting_prefix: str, name: str) -> None:
    response.set_cookie(
        name,
        "",
        max_age=0,
        expires="Thu, 01 Jan 1970 00:00:00 GMT",
        httponly=True,
        secure=_cookie_secure(setting_prefix),
        samesite=_cookie_samesite(setting_prefix),
        path="/",
        domain=_cookie_domain(setting_prefix),
    )


def set_refresh_cookie(response, refresh_token: str) -> None:
    _set_cookie(
        response,
        setting_prefix="REFRESH_TOKEN_COOKIE",
        name=get_refresh_cookie_name(),
        value=refresh_token,
        max_age=_refresh_cookie_max_age(),
    )


def clear_auth_cookies(response) -> None:
    for cookie_name in (*LEGACY_REFRESH_COOKIE_NAMES, get_refresh_cookie_name()):
        _clear_cookie(response, setting_prefix="REFRESH_TOKEN_COOKIE", name=cookie_name)


def set_mfa_temp_cookie(response, temp_token: str) -> None:
    _set_cookie(
        response,
        setting_prefix="MFA_TEMP_TOKEN_COOKIE",
        name=get_mfa_temp_cookie_name(),
        value=temp_token,
        max_age=_mfa_temp_cookie_max_age(),
    )


def clear_mfa_temp_cookie(response) -> None:
    _clear_cookie(response, setting_prefix="MFA_TEMP_TOKEN_COOKIE", name=get_mfa_temp_cookie_name())
