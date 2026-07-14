from rest_framework import serializers, status
from rest_framework.permissions import IsAuthenticated
from rest_framework.response import Response
from rest_framework.views import APIView

from application.vendors.profile.commands import RejectVendorCommand, ReinstateVendorCommand, SuspendVendorCommand
from application.vendors.shared.commands import ModeratorActor
from django_app.common.api_responses import api_success
from django_app.common.permissions import IsAdmin
from django_app.governance.marketplace_outbox import enqueue_vendor_projection, enqueue_vendor_projection_by_id
from django_app.vendors.approval_workflow import approve_pending_vendor_submission
from django_app.vendors.models import VendorProfile
from django_app.vendors.services import get_command_handlers
from django_app.vendors.views import _serialize_profile


class VendorRejectionSerializer(serializers.Serializer):
    reason = serializers.CharField(min_length=3, max_length=2000)


def _bad_request(code: str, exc: ValueError) -> Response:
    return Response(
        {"code": code, "message": str(exc), "detail": str(exc)},
        status=status.HTTP_400_BAD_REQUEST,
    )


def _moderator(request) -> ModeratorActor:
    return ModeratorActor(user_id=request.user.id)


def _current_vendor_version(vendor_id) -> int:
    return (
        VendorProfile.objects.filter(id=vendor_id)
        .values_list("version", flat=True)
        .first()
        or 0
    )


class AdminVendorApproveView(APIView):
    permission_classes = [IsAuthenticated, IsAdmin]

    def post(self, request, vendor_id):
        try:
            approval = approve_pending_vendor_submission(vendor_id)
        except ValueError as exc:
            return _bad_request("vendor_approve_failed", exc)
        message = "Vendor approved successfully."
        enqueue_vendor_projection(approval.vendor, reason="vendor_approved")
        data = _serialize_profile(approval.vendor, message=message)
        data["approval_summary"] = approval.summary()
        return api_success(
            code="vendor_approve_completed",
            message=message,
            data=data,
            request=request,
        )


class AdminVendorRejectView(APIView):
    permission_classes = [IsAuthenticated, IsAdmin]

    def post(self, request, vendor_id):
        serializer = VendorRejectionSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        try:
            profile = get_command_handlers().reject_vendor(
                RejectVendorCommand(
                    moderator=_moderator(request),
                    vendor_id=vendor_id,
                    expected_version=_current_vendor_version(vendor_id),
                    reason=serializer.validated_data["reason"],
                )
            )
            enqueue_vendor_projection_by_id(vendor_id, reason="vendor_rejected")
        except ValueError as exc:
            return _bad_request("vendor_reject_failed", exc)
        message = "Vendor rejected successfully."
        return api_success(
            code="vendor_reject_completed",
            message=message,
            data=_serialize_profile(profile, message=message),
            request=request,
        )


class AdminVendorSuspendView(APIView):
    permission_classes = [IsAuthenticated, IsAdmin]

    def post(self, request, vendor_id):
        try:
            profile = get_command_handlers().suspend_vendor(
                SuspendVendorCommand(
                    moderator=_moderator(request),
                    vendor_id=vendor_id,
                    expected_version=_current_vendor_version(vendor_id),
                )
            )
            enqueue_vendor_projection_by_id(vendor_id, reason="vendor_suspended")
        except ValueError as exc:
            return _bad_request("vendor_suspend_failed", exc)
        message = "Vendor suspended successfully."
        return api_success(
            code="vendor_suspend_completed",
            message=message,
            data=_serialize_profile(profile, message=message),
            request=request,
        )


class AdminVendorReinstateView(APIView):
    permission_classes = [IsAuthenticated, IsAdmin]

    def post(self, request, vendor_id):
        try:
            profile = get_command_handlers().reinstate_vendor(
                ReinstateVendorCommand(
                    moderator=_moderator(request),
                    vendor_id=vendor_id,
                    expected_version=_current_vendor_version(vendor_id),
                )
            )
            enqueue_vendor_projection_by_id(vendor_id, reason="vendor_reinstated")
        except ValueError as exc:
            return _bad_request("vendor_reinstate_failed", exc)
        message = "Vendor reinstated successfully."
        return api_success(
            code="vendor_reinstate_completed",
            message=message,
            data=_serialize_profile(profile, message=message),
            request=request,
        )
