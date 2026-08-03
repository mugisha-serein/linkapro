from django.core.exceptions import ImproperlyConfigured
from django.http import HttpResponse
from django.test import override_settings

from interface.identity.shared.cookies import set_refresh_cookie


@override_settings(DEBUG=False)
def test_refresh_cookie_uses_production_safe_defaults():
    response = HttpResponse()

    set_refresh_cookie(response, "refresh-token")

    cookie = response.cookies["refresh_token"]
    assert cookie.value == "refresh-token"
    assert cookie["httponly"] is True
    assert cookie["secure"] is True
    assert cookie["samesite"] == "None"
    assert cookie["path"] == "/"


@override_settings(DEBUG=False, REFRESH_TOKEN_COOKIE_SECURE=False)
def test_refresh_cookie_rejects_insecure_production_config():
    response = HttpResponse()

    try:
        set_refresh_cookie(response, "refresh-token")
    except ImproperlyConfigured as exc:
        assert "REFRESH_TOKEN_COOKIE_SECURE must be enabled in production" in str(exc)
    else:
        raise AssertionError("Expected insecure production refresh-cookie config to fail")
