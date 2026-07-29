from rest_framework import status
from rest_framework.permissions import IsAuthenticated
from rest_framework.views import APIView

from application.identity.errors import InvalidCredentialsError, UserNotFoundError
from application.identity.mfa.disable_mfa_command import DisableMfaCommand
from domain.identity.credentials import PasswordReuseNotAllowed
from interface.common.api_responses import api_error, api_success
from interface.identity.services import (
    get_change_password_use_case,
    get_disable_mfa_use_case,
    get_generate_recovery_codes_use_case,
    get_regenerate_recovery_codes_use_case,
)
from interface.identity.shared.cookies import clear_auth_cookies
from interface.identity.shared.serializers import ChangePasswordSerializer, RecoveryCodesSerializer


class ChangePasswordView(APIView):
    permission_classes = [IsAuthenticated]

    def post(self, request):
        serializer = ChangePasswordSerializer(data=request.data)
        if not serializer.is_valid():
            return api_error(
                code="password_change_validation_failed",
                message="Please fix the highlighted fields.",
                field_errors=serializer.errors,
                status=status.HTTP_400_BAD_REQUEST,
                request=request,
            )
        try:
            get_change_password_use_case().execute(serializer.to_command(user_id=request.user.id))
        except InvalidCredentialsError:
            return api_error(
                code="invalid_credentials",
                message="Invalid current password.",
                field_errors={"current_password": ["Invalid current password."]},
                status=status.HTTP_400_BAD_REQUEST,
                request=request,
            )
        except PasswordReuseNotAllowed:
            return api_error(
                code="password_change_validation_failed",
                message="Please fix the highlighted fields.",
                field_errors={"new_password": ["Choose a password you have not used recently."]},
                status=status.HTTP_400_BAD_REQUEST,
                request=request,
            )
        response = api_success(
            code="password_changed",
            message="Password changed successfully.",
            data={},
            request=request,
        )
        clear_auth_cookies(response)
        return response


class DisableMfaView(APIView):
    permission_classes = [IsAuthenticated]

    def post(self, request):
        try:
            get_disable_mfa_use_case().execute(DisableMfaCommand(user_id=request.user.id))
        except UserNotFoundError:
            return api_error(
                code="mfa_disable_failed",
                message="Unable to disable two-factor authentication.",
                status=status.HTTP_400_BAD_REQUEST,
                request=request,
            )
        return api_success(
            code="mfa_disabled",
            message="Two-factor authentication disabled.",
            data={},
            request=request,
        )


class GenerateRecoveryCodesView(APIView):
    permission_classes = [IsAuthenticated]

    def post(self, request):
        serializer = RecoveryCodesSerializer(data=request.data)
        if not serializer.is_valid():
            return api_error(
                code="recovery_codes_validation_failed",
                message="Please fix the highlighted fields.",
                field_errors=serializer.errors,
                status=status.HTTP_400_BAD_REQUEST,
                request=request,
            )
        codes = get_generate_recovery_codes_use_case().execute(
            serializer.to_generate_command(user_id=request.user.id)
        )
        return api_success(
            code="recovery_codes_generated",
            message="Recovery codes generated.",
            data={"codes": list(codes)},
            request=request,
        )


class RegenerateRecoveryCodesView(APIView):
    permission_classes = [IsAuthenticated]

    def post(self, request):
        serializer = RecoveryCodesSerializer(data=request.data)
        if not serializer.is_valid():
            return api_error(
                code="recovery_codes_validation_failed",
                message="Please fix the highlighted fields.",
                field_errors=serializer.errors,
                status=status.HTTP_400_BAD_REQUEST,
                request=request,
            )
        codes = get_regenerate_recovery_codes_use_case().execute(
            serializer.to_regenerate_command(user_id=request.user.id)
        )
        return api_success(
            code="recovery_codes_regenerated",
            message="Recovery codes regenerated.",
            data={"codes": list(codes)},
            request=request,
        )
