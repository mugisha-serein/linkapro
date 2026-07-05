from __future__ import annotations

from rest_framework import status
from rest_framework.permissions import AllowAny
from rest_framework.views import APIView

from application.identity.auth_policy import AuthenticationStatus
from application.identity.commands import LoginTwoFactorCommand
from django_app.common.api_responses import api_error, api_success
from django_app.identity.cookies import clear_auth_cookies, set_refresh_cookie
from django_app.identity.mfa_cookies import clear_mfa_temp_cookie, extract_mfa_temp_token
from django_app.identity.serializers import TwoFactorLoginSerializer
from django_app.identity.services import get_auth_session_facade
from django_app.identity.throttles import (
    TwoFactorIPThrottle,
    TwoFactorRateLimited,
    TwoFactorTempTokenThrottle,
    clear_mfa_failures,
    is_mfa_locked_out,
    record_mfa_failure,
)
from django_app.identity.views import _auth_error_response, _bootstrap_user_payload, _rate_limited_response


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

        cmd = LoginTwoFactorCommand(
            temp_token=temp_token,
            token=serializer.validated_data["token"],
        )
        session = get_auth_session_facade()
        auth_result = session.login_two_factor(cmd)
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
