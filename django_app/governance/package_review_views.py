from rest_framework import status
from rest_framework.permissions import IsAuthenticated
from rest_framework.response import Response
from rest_framework.views import APIView

from django_app.common.permissions import IsAdmin
from django_app.vendors.models import ServicePackage

from .marketplace_outbox import enqueue_vendor_projection
from .models import AuditLog
from .policy_reasons import (
    APPROVE,
    SERVICE_PACKAGE,
    generate_governance_reason,
    policy_reason_audit_details,
)
from .views import _admin_action_success, _audit, _serialize_package


def _augment_package_payload(package: ServicePackage, payload: dict) -> dict:
    payload["last_approved_at"] = package.last_approved_at.isoformat() if package.last_approved_at else None
    payload["last_vendor_public_edit_at"] = (
        package.last_vendor_public_edit_at.isoformat() if package.last_vendor_public_edit_at else None
    )
    payload["next_vendor_edit_allowed_at"] = (
        package.next_vendor_edit_allowed_at.isoformat() if package.next_vendor_edit_allowed_at else None
    )
    payload["can_edit_now"] = False if package.next_vendor_edit_allowed_at else True
    payload["package_edit_cooldown_days"] = ServicePackage.vendor_edit_cooldown_delta().days
    return payload


class AdminVendorPackageApproveView(APIView):
    permission_classes = [IsAuthenticated, IsAdmin]

    def post(self, request, package_id):
        try:
            package = ServicePackage.objects.select_related("vendor").get(id=package_id)
        except ServicePackage.DoesNotExist:
            return Response({"detail": "Package not found."}, status=status.HTTP_404_NOT_FOUND)

        package.approve()
        enqueue_vendor_projection(package.vendor, reason="package_approved")
        reason = generate_governance_reason(target_type=SERVICE_PACKAGE, action=APPROVE, target=package)
        _audit(
            request.user,
            AuditLog.ActionType.APPROVE_PACKAGE,
            "service_package",
            package.id,
            policy_reason_audit_details(reason),
        )
        payload = {"package": _augment_package_payload(package, _serialize_package(package))}
        return Response(
            _admin_action_success(
                payload,
                code="admin_package_approve_completed",
                message="Package approved.",
                reason=reason,
            )
        )
