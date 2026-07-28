import logging

from django.utils.decorators import method_decorator
from django.views.decorators.csrf import csrf_exempt
from rest_framework import status
from rest_framework.permissions import AllowAny, IsAuthenticated
from rest_framework.views import APIView

from application.identity.commands import ResetPasswordCommand, SetupPasswordCommand
from domain.identity.credentials import PasswordReuseNotAllowed, PlainPassword
from domain.identity.recovery import InvalidPasswordResetToken, PasswordResetUserInactive
from django_app.common.api_responses import api_error, api_success
from django_app.identity.password_reset_email import GENERIC_FORGOT_PASSWORD_DETAIL
from django_app.identity.session_revocation import revoke_user_sessions
from django_app.identity.services import (
    get_request_password_reset_use_case,
    get_reset_password_handler,
    get_setup_password_use_case,
)
from django_app.identity.shared.cookies import clear_auth_cookies
from django_app.identity.shared.serializers import (
    ForgotPasswordSerializer,
    ResetPasswordSerializer,
    SetupPasswordSerializer,
)
from django_app.identity.throttles import (
    ForgotPasswordEmailThrottle,
    ForgotPasswordIPThrottle,
    PasswordRecoveryRateLimited,
    PasswordResetRateLimited,
    ResetPasswordIPThrottle,
    ResetPasswordTokenThrottle,
)

from .auth import _serialize_user_profile

logger = logging.getLogger(__name__)


def _password_reset_invalid_response(field_errors):
    return api_error(
        code="password_reset_validation_failed",
        message="Please fix the highlighted fields.",
        field_errors=field_errors,
        status=status.HTTP_400_BAD_REQUEST,
    )


def _password_reset_token_invalid_response():
    return api_error(
        code="password_reset_token_invalid",
        message="This reset link has expired or is invalid.",
        field_errors={"token": ["Invalid or expired reset token."]},
        status=status.HTTP_400_BAD_REQUEST,
    )


def _client_ip(request):
    forwarded_for = request.META.get("HTTP_X_FORWARDED_FOR", "")
    if forwarded_for:
        return forwarded_for.split(",", 1)[0].strip()
    return request.META.get("REMOTE_ADDR", "")


class SetupPasswordView(APIView):
    permission_classes = [IsAuthenticated]

    def post(self, request):
        serializer = SetupPasswordSerializer(data=request.data)
        if not serializer.is_valid():
            return api_error(
                code="password_setup_validation_failed",
                message="Please fix the highlighted fields.",
                field_errors=serializer.errors,
                status=status.HTTP_400_BAD_REQUEST,
                request=request,
            )
        try:
            user_dto = get_setup_password_use_case().execute(
                SetupPasswordCommand(
                    user_id=request.user.id,
                    plain_password=PlainPassword(serializer.validated_data["password"]),
                )
            )
        except PasswordReuseNotAllowed:
            return api_error(
                code="password_setup_validation_failed",
                message="Please fix the highlighted fields.",
                field_errors={"password": ["Choose a password you have not used recently."]},
                status=status.HTTP_400_BAD_REQUEST,
                request=request,
            )
        return api_success(
            code="password_setup_completed",
            message="Password set successfully.",
            data={
                "user": _serialize_user_profile(user_dto),
                "role": user_dto.role,
                "next_path": "/dashboard" if user_dto.role == "planner" else f"/{user_dto.role}/dashboard",
                "requires_password_setup": False,
                "vendor_profile": None,
            },
            request=request,
        )


@method_decorator(csrf_exempt, name="dispatch")
class ForgotPasswordView(APIView):
    permission_classes = [AllowAny]
    throttle_classes = [ForgotPasswordIPThrottle, ForgotPasswordEmailThrottle]

    def throttled(self, request, wait):
        raise PasswordRecoveryRateLimited(wait)

    def post(self, request):
        serializer = ForgotPasswordSerializer(data=request.data)
        if not serializer.is_valid():
            return api_error(
                code="password_recovery_validation_failed",
                message="Please fix the highlighted fields.",
                field_errors=serializer.errors,
                status=status.HTTP_400_BAD_REQUEST,
            )
        email = serializer.validated_data["email"].strip().lower()
        try:
            get_request_password_reset_use_case().execute(email=email)
        except Exception as exc:
            logger.error(
                "forgot_password_email_dispatch_deferred",
                extra={"email_domain": email.rsplit("@", 1)[-1], "error_type": exc.__class__.__name__},
                exc_info=True,
            )

        return api_success(
            code="password_reset_email_queued",
            message=GENERIC_FORGOT_PASSWORD_DETAIL,
            data={},
            status=status.HTTP_202_ACCEPTED,
            extra={"detail": GENERIC_FORGOT_PASSWORD_DETAIL},
        )


@method_decorator(csrf_exempt, name="dispatch")
class ResetPasswordView(APIView):
    permission_classes = [AllowAny]
    throttle_classes = [ResetPasswordIPThrottle, ResetPasswordTokenThrottle]

    def throttled(self, request, wait):
        raise PasswordResetRateLimited(wait)

    def post(self, request):
        serializer = ResetPasswordSerializer(data=request.data)
        if not serializer.is_valid():
            logger.info(
                "reset_password_validation_failed",
                extra={"field_error_keys": list(serializer.errors.keys())},
            )
            return _password_reset_invalid_response(serializer.errors)

        try:
            result = get_reset_password_handler().handle(
                ResetPasswordCommand(
                    token=serializer.validated_data["token"],
                    new_password=serializer.validated_data["new_password"],
                    client_ip=_client_ip(request),
                    user_agent=request.META.get("HTTP_USER_AGENT", ""),
                )
            )
        except (InvalidPasswordResetToken, PasswordResetUserInactive):
            logger.info("reset_password_invalid_token")
            return _password_reset_token_invalid_response()
        except PasswordReuseNotAllowed:
            logger.info("reset_password_reused_password_rejected")
            return _password_reset_invalid_response(
                {"new_password": ["Choose a password you have not used recently."]}
            )

        logger.info("password_reset_token_consumed", extra={"user_id": str(result.user_id)})
        response = api_success(
            code="password_reset_completed",
            message="Password updated successfully.",
            data={"status": "password_reset"},
            status=status.HTTP_200_OK,
            extra={"status": "password_reset"},
        )
        clear_auth_cookies(response)
        return response


class SessionRevokingSetupPasswordView(SetupPasswordView):
    def post(self, request):
        response = super().post(request)
        if 200 <= response.status_code < 300:
            revoke_user_sessions(request.user.id, reason="password_setup")
            clear_auth_cookies(response)
        return response
