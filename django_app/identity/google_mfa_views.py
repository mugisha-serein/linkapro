from __future__ import annotations

from django.shortcuts import redirect
from django.views import View

from application.identity.auth_policy import AuthenticationStatus
from application.identity.oauth_state import (
    OAUTH_STATE_COOKIE_NAME,
    clear_oauth_state_cookie,
    consume_oauth_state,
    set_oauth_state_cookie,
    issue_oauth_state,
)
from django_app.identity.cookies import clear_auth_cookies, set_refresh_cookie
from django_app.identity.mfa_cookies import clear_mfa_temp_cookie, set_mfa_temp_cookie
from django_app.identity.services import get_auth_session_facade, get_google_oauth_adapter
from django_app.identity.views import _frontend_url, _no_store_redirect, _redirect_error


class GoogleLoginView(View):
    def get(self, request):
        from application.identity.oauth_state import ALLOWED_OAUTH_SIGNUP_ROLES

        signup_role = (request.GET.get("role") or "").strip().lower()
        if signup_role not in ALLOWED_OAUTH_SIGNUP_ROLES:
            return _redirect_error("invalid_role")

        adapter = get_google_oauth_adapter()
        try:
            challenge = issue_oauth_state(signup_role)
            auth_url = adapter.build_auth_url(state=challenge.state)
        except Exception:
            return _redirect_error("oauth_not_configured")
        response = redirect(auth_url)
        set_oauth_state_cookie(response, challenge)
        return response


class GoogleCallbackView(View):
    def get(self, request):
        oauth_error = request.GET.get("error")
        if oauth_error:
            response = _redirect_error(oauth_error)
            clear_oauth_state_cookie(response)
            clear_auth_cookies(response)
            clear_mfa_temp_cookie(response)
            return response

        code = request.GET.get("code")
        if not code:
            response = _redirect_error("missing_code")
            clear_oauth_state_cookie(response)
            clear_auth_cookies(response)
            clear_mfa_temp_cookie(response)
            return response
        frontend_url = _frontend_url()

        state_result = consume_oauth_state(
            request.GET.get("state"),
            request.COOKIES.get(OAUTH_STATE_COOKIE_NAME),
        )
        if not state_result:
            response = _redirect_error("oauth_failed")
            clear_oauth_state_cookie(response)
            clear_auth_cookies(response)
            clear_mfa_temp_cookie(response)
            return response

        adapter = get_google_oauth_adapter()
        try:
            token_data = adapter.exchange_code(code)
            user_data = adapter.get_user_info(token_data["access_token"])
            result = get_auth_session_facade().oauth_login(
                user_data,
                token_data,
                signup_role=state_result.role,
            )
        except Exception:
            response = _redirect_error("oauth_failed")
            clear_oauth_state_cookie(response)
            clear_auth_cookies(response)
            clear_mfa_temp_cookie(response)
            return response

        if result.requires_2fa:
            response = _no_store_redirect(f"{frontend_url}/auth/2fa")
            clear_oauth_state_cookie(response)
            clear_auth_cookies(response)
            if result.temp_token:
                set_mfa_temp_cookie(response, result.temp_token)
            return response

        response = _no_store_redirect(f"{frontend_url}/auth/success")
        clear_oauth_state_cookie(response)
        clear_mfa_temp_cookie(response)
        if result.refresh:
            set_refresh_cookie(response, result.refresh)
        return response
