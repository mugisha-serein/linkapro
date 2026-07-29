from __future__ import annotations

import base64
from io import BytesIO

import qrcode
from django.shortcuts import redirect
from django.views import View
from rest_framework import status
from rest_framework.permissions import AllowAny, IsAuthenticated
from rest_framework.views import APIView

from application.identity.authentication import AuthenticationStatus
from application.identity.authentication.complete_mfa_login_command import LoginTwoFactorCommand
from application.identity.mfa.begin_mfa_enrollment_command import EnableTwoFactorCommand
from application.identity.mfa.confirm_mfa_enrollment_command import VerifyTwoFactorSetupCommand
from application.identity.errors import InvalidTwoFactorCodeError, UserNotFoundError
from domain.identity.account import AccountRole
from django_app.identity.shared.oauth_state import (
    OAUTH_STATE_COOKIE_NAME,
    clear_oauth_state_cookie,
    consume_oauth_state,
    issue_oauth_state,
    set_oauth_state_cookie,
)
from django_app.common.api_responses import api_error, api_success
from django_app.identity.services import get_command_handlers, get_google_login_use_case, get_google_oauth_adapter
from django_app.identity.shared.cookies import (
    clear_auth_cookies,
    clear_mfa_temp_cookie,
    extract_mfa_temp_token,
    set_mfa_temp_cookie,
    set_refresh_cookie,
)
from django_app.identity.shared.serializers import TwoFactorLoginSerializer, TwoFactorSetupVerifySerializer
from django_app.identity.throttles import (
    GoogleOAuthIPThrottle,
    TwoFactorIPThrottle,
    TwoFactorRateLimited,
    TwoFactorTempTokenThrottle,
    clear_mfa_failures,
    is_mfa_locked_out,
    record_mfa_failure,
)

from .auth import (
    _auth_error_response,
    _bootstrap_user_payload,
    _frontend_url,
    _no_store_redirect,
    _rate_limited_response,
    _redirect_error,
)


def _qr_code_base64(value: str) -> str:
    img = qrcode.make(value)
    buffer = BytesIO()
    img.save(buffer, format="PNG")
    return base64.b64encode(buffer.getvalue()).decode()


class EnableTwoFactorView(APIView):
    permission_classes = [IsAuthenticated]

    def post(self, request):
        cmd = EnableTwoFactorCommand(user_id=request.user.id)
        handlers = get_command_handlers()
        try:
            setup_dto = handlers.enable_two_factor(cmd)
            return api_success(
                code="mfa_setup_started",
                message="Two-factor setup started.",
                data={
                    "enrollment_id": setup_dto.enrollment_id,
                    "secret": setup_dto.secret,
                    "provisioning_uri": setup_dto.provisioning_uri,
                    "qr_code_base64": _qr_code_base64(setup_dto.provisioning_uri),
                },
                request=request,
            )
        except UserNotFoundError:
            return api_error(
                code="mfa_setup_failed",
                message="Unable to start two-factor setup.",
                status=status.HTTP_400_BAD_REQUEST,
                request=request,
            )


class VerifyTwoFactorSetupView(APIView):
    permission_classes = [IsAuthenticated]

    def post(self, request):
        serializer = TwoFactorSetupVerifySerializer(data=request.data)
        if not serializer.is_valid():
            return api_error(
                code="mfa_setup_validation_failed",
                message="Please fix the highlighted fields.",
                field_errors=serializer.errors,
                status=status.HTTP_400_BAD_REQUEST,
                request=request,
            )
        cmd = VerifyTwoFactorSetupCommand(
            user_id=request.user.id,
            token=serializer.verification_code(),
        )
        handlers = get_command_handlers()
        try:
            handlers.verify_two_factor_setup(cmd)
            return api_success(
                code="mfa_enabled",
                message="Two-factor authentication enabled.",
                data={},
                request=request,
            )
        except InvalidTwoFactorCodeError:
            return api_error(
                code="mfa_setup_verification_failed",
                message="Invalid verification code.",
                field_errors={"token": ["Invalid verification code."]},
                status=status.HTTP_400_BAD_REQUEST,
                request=request,
            )


class LoginTwoFactorView(APIView):
    permission_classes = [AllowAny]
    throttle_classes = [TwoFactorIPThrottle, TwoFactorTempTokenThrottle]

    def throttled(self, request, wait):
        raise TwoFactorRateLimited(wait=wait, request=request)

    def post(self, request):
        data = request.data.copy()
        if not data.get("temp_token"):
            temp_token_from_cookie = extract_mfa_temp_token(request)
            if temp_token_from_cookie:
                data["temp_token"] = temp_token_from_cookie

        serializer = TwoFactorLoginSerializer(data=data)
        if not serializer.is_valid():
            return api_error(
                code="mfa_validation_failed",
                message="Please fix the highlighted fields.",
                field_errors=serializer.errors,
                status=status.HTTP_400_BAD_REQUEST,
                request=request,
            )

        temp_token = serializer.validated_data["temp_token"]
        if is_mfa_locked_out(request, temp_token):
            return _rate_limited_response(
                code="mfa_rate_limited",
                message="Too many verification attempts. Please try again later.",
                request=request,
            )

        cmd = serializer.to_command()
        auth_result = get_command_handlers().login_two_factor(cmd)
        if auth_result.status is not AuthenticationStatus.AUTHENTICATED:
            record_mfa_failure(request, temp_token, auth_status=auth_result.status)
            response = _auth_error_response(auth_result.status, request=request)
            clear_auth_cookies(response)
            return response

        user = auth_result.user
        clear_mfa_failures(request, temp_token, user_id=getattr(user, "id", None))
        response = api_success(
            code="mfa_login_completed",
            message="Signed in successfully.",
            data={
                "access": auth_result.access_token,
                "token_type": "Bearer",
                "user": auth_result.bootstrap_user or _bootstrap_user_payload(user),
            },
            status=status.HTTP_200_OK,
            request=request,
        )
        clear_mfa_temp_cookie(response)
        set_refresh_cookie(response, auth_result.refresh_token)
        return response


def _result_refresh_token(result) -> str | None:
    return getattr(result, "refresh_token", None) or getattr(result, "refresh", None)


def _allow_google_oauth_request(request, view) -> bool:
    return GoogleOAuthIPThrottle().allow_request(request, view)


class GoogleLoginView(View):
    def get(self, request):
        if not _allow_google_oauth_request(request, self):
            return _redirect_error("oauth_rate_limited")

        from django_app.identity.shared.oauth_state import ALLOWED_OAUTH_SIGNUP_ROLES

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
        if not _allow_google_oauth_request(request, self):
            return _redirect_error("oauth_rate_limited")

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
            signup_role = AccountRole(state_result.role)
            command = adapter.build_login_command(code, signup_role=signup_role)
            result = get_google_login_use_case().execute(command)
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
        refresh_token = _result_refresh_token(result)
        if refresh_token:
            set_refresh_cookie(response, refresh_token)
        return response
