from rest_framework import status
from rest_framework.permissions import IsAuthenticated
from rest_framework.response import Response
from rest_framework.views import APIView

from django_app.common.permissions import IsAdmin
from django_app.vendors.approval_workflow import approve_pending_vendor_submission

from .models import AuditLog
from .views import _admin_action_error, _admin_action_success, _audit, _serialize_vendor, _sync_approved_vendor


class AdminVendorApproveView(APIView):
    permission_classes = [IsAuthenticated, IsAdmin]

    def post(self, request, vendor_id):
        try:
            approval = approve_pending_vendor_submission(vendor_id)
        except ValueError as exc:
            return _admin_action_error("vendor_approve_failed", str(exc), status.HTTP_400_BAD_REQUEST)

        _sync_approved_vendor(approval.vendor)
        _audit(
            request.user,
            AuditLog.ActionType.APPROVE_VENDOR,
            "vendor_profile",
            approval.vendor.id,
            approval.summary(),
        )
        payload = _serialize_vendor(approval.vendor)
        payload["approval_summary"] = approval.summary()
        return Response(
            _admin_action_success(
                payload,
                code="vendor_approve_completed",
                message="Vendor approved successfully.",
            )
        )
