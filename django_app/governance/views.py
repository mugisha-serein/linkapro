from rest_framework.views import APIView
from rest_framework.response import Response
from rest_framework import status
from rest_framework.permissions import IsAuthenticated
from django_app.common.permissions import IsAdmin
from django_app.identity.models import User
from django_app.events.models import Event
from django_app.vendors.models import ServicePackage, VendorProfile
from infrastructure.adapters.marketplace_projection import (
    delete_vendor_from_marketplace,
    sync_vendor_to_marketplace,
)
from .models import AuditLog, ContentFlag
from .serializers import FlagContentSerializer
from .services import get_command_handlers, get_query_handlers
from application.governance.commands import FlagContentCommand

VENDOR_ADMIN_STATUSES = {choice[0] for choice in VendorProfile.Status.choices}


class FlagContentCreateView(APIView):
    permission_classes = [IsAuthenticated]

    def post(self, request):
        serializer = FlagContentSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)

        cmd = FlagContentCommand(
            reported_by=request.user.id,
            content_type=serializer.validated_data["content_type"],
            content_id=serializer.validated_data["content_id"],
            reason=serializer.validated_data["reason"],
        )

        handlers = get_command_handlers()
        flag_dto = handlers.flag_content(cmd)

        return Response({
            "id": str(flag_dto.id),
            "status": flag_dto.status,
            "message": "Content flagged successfully. Our team will review it."
        }, status=status.HTTP_201_CREATED)


class AdminMetricsView(APIView):
    permission_classes = [IsAuthenticated, IsAdmin]

    def get(self, request):
        query_handlers = get_query_handlers()
        latest = query_handlers.get_latest_metrics()

        if latest:
            return Response(
                {
                    "total_users": latest.total_users,
                    "active_vendors": latest.active_vendors,
                    "payments_today": 0,
                    "fraud_signals": 0,
                    "total_events": latest.total_events,
                    "total_vendors": latest.total_vendors,
                    "vendor_status_counts": _vendor_status_counts(),
                    "revenue": "0",
                    "pending_vendor_approvals": latest.pending_vendor_approvals,
                }
            )

        return Response(
            {
                "total_users": User.objects.count(),
                "active_vendors": VendorProfile.objects.filter(status=VendorProfile.Status.APPROVED).count(),
                "vendor_status_counts": _vendor_status_counts(),
                "payments_today": 0,
                "fraud_signals": 0,
                "total_events": Event.objects.count(),
                "total_vendors": VendorProfile.objects.count(),
                "revenue": "0",
                "pending_vendor_approvals": VendorProfile.objects.filter(
                    status=VendorProfile.Status.PENDING_REVIEW
                ).count(),
            }
        )


def _serialize_user(user: User) -> dict:
    return {
        "id": str(user.id),
        "email": user.email,
        "first_name": user.first_name,
        "last_name": user.last_name,
        "role": user.role,
        "is_active": user.is_active,
        "is_verified": user.is_verified,
        "created_at": user.created_at.isoformat(),
        "updated_at": user.updated_at.isoformat(),
    }


def _serialize_vendor(vendor: VendorProfile) -> dict:
    return {
        "id": str(vendor.id),
        "user_id": str(vendor.user_id),
        "business_name": vendor.business_name,
        "category": vendor.category,
        "description": vendor.description,
        "service_area": vendor.service_area,
        "contact_email": vendor.contact_email,
        "contact_phone": vendor.contact_phone,
        "website": vendor.website,
        "status": vendor.status,
        "submitted_at": vendor.submitted_at.isoformat() if vendor.submitted_at else None,
        "approved_at": vendor.approved_at.isoformat() if vendor.approved_at else None,
        "rejected_at": vendor.rejected_at.isoformat() if vendor.rejected_at else None,
        "rejection_reason": vendor.rejection_reason,
    }


def _serialize_package(package: ServicePackage) -> dict:
    return {
        "id": str(package.id),
        "vendor_id": str(package.vendor_id),
        "vendor_business_name": package.vendor.business_name,
        "name": package.name,
        "description": package.description,
        "price": str(package.price),
        "currency": package.currency,
        "package_tier": package.package_tier,
        "approval_status": package.approval_status,
        "rejection_reason": package.rejection_reason,
        "is_active": package.is_active,
        "is_deleted": package.is_deleted,
        "deleted_at": package.deleted_at.isoformat() if package.deleted_at else None,
        "created_at": package.created_at.isoformat(),
        "updated_at": package.updated_at.isoformat(),
    }


def _vendor_status_counts() -> dict:
    return {
        status_value: VendorProfile.objects.filter(status=status_value).count()
        for status_value in VENDOR_ADMIN_STATUSES
    }


def _serialize_flag(flag: ContentFlag) -> dict:
    return {
        "id": str(flag.id),
        "content_type": flag.content_type,
        "content_id": str(flag.content_id),
        "reason": flag.reason,
        "status": flag.status,
        "admin_notes": flag.admin_notes,
        "reported_by": str(flag.reported_by_id),
        "created_at": flag.created_at.isoformat(),
        "updated_at": flag.updated_at.isoformat(),
    }


def _serialize_audit_log(log: AuditLog) -> dict:
    return {
        "id": str(log.id),
        "admin": str(log.admin_id) if log.admin_id else None,
        "action_type": log.action_type,
        "target_type": log.target_type,
        "target_id": str(log.target_id),
        "details": log.details,
        "created_at": log.created_at.isoformat(),
    }


def _audit(admin, action_type: str, target_type: str, target_id, details: dict | None = None) -> None:
    AuditLog.objects.create(
        admin=admin,
        action_type=action_type,
        target_type=target_type,
        target_id=target_id,
        details=details or {},
    )


def _sync_approved_vendor(vendor: VendorProfile) -> None:
    sync_vendor_to_marketplace(vendor)


def _delete_vendor_listing(vendor: VendorProfile) -> None:
    delete_vendor_from_marketplace(vendor.id)


class AdminUserListView(APIView):
    permission_classes = [IsAuthenticated, IsAdmin]

    def get(self, request):
        users = User.objects.order_by("-created_at")
        role = request.query_params.get("role")
        if role:
            users = users.filter(role=role)

        return Response({"results": [_serialize_user(user) for user in users], "count": users.count()})


class AdminVendorListView(APIView):
    permission_classes = [IsAuthenticated, IsAdmin]

    def get(self, request):
        vendors = VendorProfile.objects.select_related("user").order_by("-updated_at", "-created_at")
        status_filter = request.query_params.get("status")
        if status_filter and status_filter != "all":
            if status_filter not in VENDOR_ADMIN_STATUSES:
                return Response({"detail": "Invalid vendor status."}, status=status.HTTP_400_BAD_REQUEST)
            vendors = vendors.filter(status=status_filter)

        search = (request.query_params.get("search") or "").strip()
        if search:
            vendors = vendors.filter(business_name__icontains=search)

        return Response({
            "results": [_serialize_vendor(vendor) for vendor in vendors],
            "count": vendors.count(),
            "status_counts": _vendor_status_counts(),
        })


class AdminUserBanView(APIView):
    permission_classes = [IsAuthenticated, IsAdmin]

    def post(self, request, user_id):
        try:
            user = User.objects.get(id=user_id)
        except User.DoesNotExist:
            return Response({"detail": "User not found."}, status=status.HTTP_404_NOT_FOUND)

        user.is_active = False
        user.save(update_fields=["is_active", "updated_at"])
        _audit(request.user, AuditLog.ActionType.BAN_USER, "user", user.id)
        return Response(_serialize_user(user))


class AdminUserReinstateView(APIView):
    permission_classes = [IsAuthenticated, IsAdmin]

    def post(self, request, user_id):
        try:
            user = User.objects.get(id=user_id)
        except User.DoesNotExist:
            return Response({"detail": "User not found."}, status=status.HTTP_404_NOT_FOUND)

        user.is_active = True
        user.save(update_fields=["is_active", "updated_at"])
        _audit(request.user, AuditLog.ActionType.REINSTATE_USER, "user", user.id)
        return Response(_serialize_user(user))


class AdminVendorApproveView(APIView):
    permission_classes = [IsAuthenticated, IsAdmin]

    def post(self, request, vendor_id):
        try:
            vendor = VendorProfile.objects.get(id=vendor_id)
        except VendorProfile.DoesNotExist:
            return Response({"detail": "Vendor not found."}, status=status.HTTP_404_NOT_FOUND)
        if vendor.status != VendorProfile.Status.PENDING_REVIEW:
            return Response(
                {"detail": "Vendor must be submitted for review before approval."},
                status=status.HTTP_400_BAD_REQUEST,
            )

        from django.utils import timezone

        vendor.status = VendorProfile.Status.APPROVED
        vendor.approved_at = timezone.now()
        vendor.rejected_at = None
        vendor.rejection_reason = None
        vendor.save(update_fields=["status", "approved_at", "rejected_at", "rejection_reason", "updated_at"])
        _sync_approved_vendor(vendor)
        _audit(request.user, AuditLog.ActionType.APPROVE_VENDOR, "vendor_profile", vendor.id)
        return Response(_serialize_vendor(vendor))


class AdminVendorRejectView(APIView):
    permission_classes = [IsAuthenticated, IsAdmin]

    def post(self, request, vendor_id):
        reason = request.data.get("reason") or "Rejected by administrator."
        try:
            vendor = VendorProfile.objects.get(id=vendor_id)
        except VendorProfile.DoesNotExist:
            return Response({"detail": "Vendor not found."}, status=status.HTTP_404_NOT_FOUND)
        if vendor.status != VendorProfile.Status.PENDING_REVIEW:
            return Response(
                {"detail": "Only vendors waiting for review can be rejected."},
                status=status.HTTP_400_BAD_REQUEST,
            )

        from django.utils import timezone

        vendor.status = VendorProfile.Status.REJECTED
        vendor.rejected_at = timezone.now()
        vendor.rejection_reason = reason
        vendor.save(update_fields=["status", "rejected_at", "rejection_reason", "updated_at"])
        _delete_vendor_listing(vendor)
        _audit(request.user, AuditLog.ActionType.REJECT_VENDOR, "vendor_profile", vendor.id, {"reason": reason})
        return Response(_serialize_vendor(vendor))


class AdminVendorSuspendView(APIView):
    permission_classes = [IsAuthenticated, IsAdmin]

    def post(self, request, vendor_id):
        try:
            vendor = VendorProfile.objects.get(id=vendor_id)
        except VendorProfile.DoesNotExist:
            return Response({"detail": "Vendor not found."}, status=status.HTTP_404_NOT_FOUND)
        if vendor.status != VendorProfile.Status.APPROVED:
            return Response(
                {"detail": "Only approved vendors can be suspended."},
                status=status.HTTP_400_BAD_REQUEST,
            )

        vendor.status = VendorProfile.Status.SUSPENDED
        vendor.save(update_fields=["status", "updated_at"])
        _delete_vendor_listing(vendor)
        _audit(request.user, AuditLog.ActionType.SUSPEND_VENDOR, "vendor_profile", vendor.id)
        return Response(_serialize_vendor(vendor))


class AdminVendorReinstateView(APIView):
    permission_classes = [IsAuthenticated, IsAdmin]

    def post(self, request, vendor_id):
        try:
            vendor = VendorProfile.objects.get(id=vendor_id)
        except VendorProfile.DoesNotExist:
            return Response({"detail": "Vendor not found."}, status=status.HTTP_404_NOT_FOUND)
        if vendor.status != VendorProfile.Status.SUSPENDED:
            return Response(
                {"detail": "Only suspended vendors can be reinstated."},
                status=status.HTTP_400_BAD_REQUEST,
            )

        from django.utils import timezone

        vendor.status = VendorProfile.Status.APPROVED
        vendor.approved_at = timezone.now()
        vendor.save(update_fields=["status", "approved_at", "updated_at"])
        _sync_approved_vendor(vendor)
        _audit(request.user, AuditLog.ActionType.APPROVE_VENDOR, "vendor_profile", vendor.id, {"from": "suspended"})
        return Response(_serialize_vendor(vendor))


class AdminVendorPackagePendingListView(APIView):
    permission_classes = [IsAuthenticated, IsAdmin]

    def get(self, request):
        packages = (
            ServicePackage.objects.select_related("vendor")
            .filter(approval_status=ServicePackage.ApprovalStatus.WAITING_APPROVAL)
            .order_by("-updated_at", "-created_at")
        )
        return Response({"results": [_serialize_package(package) for package in packages], "count": packages.count()})


class AdminVendorPackageApproveView(APIView):
    permission_classes = [IsAuthenticated, IsAdmin]

    def post(self, request, package_id):
        try:
            package = ServicePackage.objects.select_related("vendor").get(id=package_id)
        except ServicePackage.DoesNotExist:
            return Response({"detail": "Package not found."}, status=status.HTTP_404_NOT_FOUND)

        package.approval_status = ServicePackage.ApprovalStatus.APPROVED
        package.rejection_reason = None
        package.is_active = True
        package.save(update_fields=["approval_status", "rejection_reason", "is_active", "updated_at"])
        _audit(request.user, AuditLog.ActionType.APPROVE_PACKAGE, "service_package", package.id)
        return Response({"message": "Package approved.", "package": _serialize_package(package)})


class AdminVendorPackageRejectView(APIView):
    permission_classes = [IsAuthenticated, IsAdmin]

    def post(self, request, package_id):
        reason = request.data.get("reason") or "Package rejected by administrator."
        try:
            package = ServicePackage.objects.select_related("vendor").get(id=package_id)
        except ServicePackage.DoesNotExist:
            return Response({"detail": "Package not found."}, status=status.HTTP_404_NOT_FOUND)

        package.approval_status = ServicePackage.ApprovalStatus.REJECTED
        package.rejection_reason = reason
        package.is_active = False
        package.save(update_fields=["approval_status", "rejection_reason", "is_active", "updated_at"])
        _audit(request.user, AuditLog.ActionType.REJECT_PACKAGE, "service_package", package.id, {"reason": reason})
        return Response({"message": "Package rejected.", "package": _serialize_package(package)})


class AdminVendorPackageHardDeleteView(APIView):
    permission_classes = [IsAuthenticated, IsAdmin]

    def delete(self, request, package_id):
        try:
            package = ServicePackage.all_objects.select_related("vendor").get(id=package_id)
        except ServicePackage.DoesNotExist:
            return Response({"detail": "Package not found."}, status=status.HTTP_404_NOT_FOUND)

        package_id_value = package.id
        _audit(request.user, AuditLog.ActionType.HARD_DELETE_PACKAGE, "service_package", package_id_value)
        package.hard_delete()
        return Response({"message": "Package permanently deleted.", "package_id": str(package_id_value)})


class AdminFlagListView(APIView):
    permission_classes = [IsAuthenticated, IsAdmin]

    def get(self, request):
        flags = ContentFlag.objects.select_related("reported_by").order_by("-created_at")
        return Response([_serialize_flag(flag) for flag in flags])


class AdminFlagResolveView(APIView):
    permission_classes = [IsAuthenticated, IsAdmin]

    def post(self, request, flag_id):
        try:
            flag = ContentFlag.objects.get(id=flag_id)
        except ContentFlag.DoesNotExist:
            return Response({"detail": "Flag not found."}, status=status.HTTP_404_NOT_FOUND)

        dismiss = bool(request.data.get("dismiss", False))
        flag.status = ContentFlag.Status.DISMISSED if dismiss else ContentFlag.Status.REVIEWED
        flag.admin_notes = request.data.get("notes") or ""
        flag.save(update_fields=["status", "admin_notes", "updated_at"])
        _audit(
            request.user,
            AuditLog.ActionType.FLAG_RESOLVE,
            "content_flag",
            flag.id,
            {"dismiss": dismiss, "notes": flag.admin_notes},
        )
        return Response(_serialize_flag(flag))


class AdminAuditLogListView(APIView):
    permission_classes = [IsAuthenticated, IsAdmin]

    def get(self, request):
        logs = AuditLog.objects.select_related("admin").order_by("-created_at")
        return Response([_serialize_audit_log(log) for log in logs[:200]])
