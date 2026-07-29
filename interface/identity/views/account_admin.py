from rest_framework import status
from rest_framework.views import APIView

from application.identity.errors import UserNotFoundError
from domain.identity.authorization import AuthorizationError
from interface.common.api_responses import api_error, api_success
from interface.common.permissions import IsAdmin
from interface.identity.services import (
    get_assign_role_use_case,
    get_reactivate_account_use_case,
    get_suspend_account_use_case,
    get_unlock_account_use_case,
)
from interface.identity.shared.serializers import (
    AssignRoleSerializer,
    ReactivateAccountSerializer,
    SuspendAccountSerializer,
    UnlockAccountSerializer,
)


def _admin_validation_error(serializer, request):
    return api_error(
        code="account_administration_validation_failed",
        message="Please fix the highlighted fields.",
        field_errors=serializer.errors,
        status=status.HTTP_400_BAD_REQUEST,
        request=request,
    )


def _admin_error(exc, request):
    if isinstance(exc, UserNotFoundError):
        return api_error(
            code="account_not_found",
            message="Account not found.",
            status=status.HTTP_404_NOT_FOUND,
            request=request,
        )
    if isinstance(exc, AuthorizationError):
        return api_error(
            code="account_administration_forbidden",
            message="You are not allowed to perform this account action.",
            status=status.HTTP_403_FORBIDDEN,
            request=request,
        )
    return api_error(
        code="account_administration_failed",
        message="Unable to update account.",
        status=status.HTTP_400_BAD_REQUEST,
        request=request,
    )


class AssignRoleView(APIView):
    permission_classes = [IsAdmin]

    def post(self, request, user_id):
        serializer = AssignRoleSerializer(data=request.data)
        if not serializer.is_valid():
            return _admin_validation_error(serializer, request)
        try:
            get_assign_role_use_case().execute(
                serializer.to_command(actor_id=request.user.id, target_user_id=user_id)
            )
        except Exception as exc:
            return _admin_error(exc, request)
        return api_success(
            code="role_assigned",
            message="Role assigned.",
            data={},
            request=request,
        )


class SuspendAccountView(APIView):
    permission_classes = [IsAdmin]

    def post(self, request, user_id):
        serializer = SuspendAccountSerializer(data=request.data)
        if not serializer.is_valid():
            return _admin_validation_error(serializer, request)
        try:
            get_suspend_account_use_case().execute(
                serializer.to_command(actor_id=request.user.id, target_user_id=user_id)
            )
        except Exception as exc:
            return _admin_error(exc, request)
        return api_success(
            code="account_suspended",
            message="Account suspended.",
            data={},
            request=request,
        )


class ReactivateAccountView(APIView):
    permission_classes = [IsAdmin]

    def post(self, request, user_id):
        serializer = ReactivateAccountSerializer(data=request.data)
        if not serializer.is_valid():
            return _admin_validation_error(serializer, request)
        try:
            get_reactivate_account_use_case().execute(
                serializer.to_command(actor_id=request.user.id, target_user_id=user_id)
            )
        except Exception as exc:
            return _admin_error(exc, request)
        return api_success(
            code="account_reactivated",
            message="Account reactivated.",
            data={},
            request=request,
        )


class UnlockAccountView(APIView):
    permission_classes = [IsAdmin]

    def post(self, request, user_id):
        serializer = UnlockAccountSerializer(data=request.data)
        if not serializer.is_valid():
            return _admin_validation_error(serializer, request)
        try:
            get_unlock_account_use_case().execute(
                serializer.to_command(actor_id=request.user.id, target_user_id=user_id)
            )
        except Exception as exc:
            return _admin_error(exc, request)
        return api_success(
            code="account_unlocked",
            message="Account unlocked.",
            data={},
            request=request,
        )
