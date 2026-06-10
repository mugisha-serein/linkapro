from django.conf import settings


def set_refresh_cookie(response, refresh_token: str) -> None:
    response.set_cookie(
        "refresh_token",
        refresh_token,
        max_age=int(settings.SIMPLE_JWT["REFRESH_TOKEN_LIFETIME"].total_seconds()),
        httponly=True,
        secure=not settings.DEBUG,
        # SameSite=None is required for cross-origin cookie delivery
        # (frontend on Vercel → backend on Render). Requires Secure=True.
        samesite="None" if not settings.DEBUG else "Lax",
        path="/",
    )


def clear_auth_cookies(response) -> None:
    response.delete_cookie("access_token", path="/")
    response.delete_cookie(
        "refresh_token",
        path="/",
        secure=not settings.DEBUG,
        samesite="None" if not settings.DEBUG else "Lax",
    )
