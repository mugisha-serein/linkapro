from rest_framework.views import APIView
from rest_framework.response import Response
from rest_framework import status
from rest_framework.permissions import IsAuthenticated
from django_app.common.permissions import IsAdmin
from django_app.identity.models import User
from django_app.events.models import Event
from django_app.vendors.models import VendorProfile
from .models import AuditLog, ContentFlag
from .serializers import FlagContentSerializer
from .services import get_command_handlers, get_query_handlers
from application.governance.commands import FlagContentCommand


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
                    "revenue": "0",
                    "pending_vendor_approvals": latest.pending_vendor_approvals,
                }
            )

        return Response(
            {
                "total_users": User.objects.count(),
                "active_vendors": VendorProfile.objects.filter(status=VendorProfile.Status.APPROVED).count(),
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


class AdminUserListView(APIView):
    permission_classes = [IsAuthenticated, IsAdmin]

    def get(self, request):
        users = User.objects.order_by("-created_at")
        role = request.query_params.get("role")
        if role:
            users = users.filter(role=role)

        return Response({"results": [_serialize_user(user) for user in users], "count": users.count()})


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
        from tasks.marketplace_sync import sync_vendor_listing_to_fastapi

        sync_vendor_listing_to_fastapi(
            str(vendor.id),
            vendor.business_name,
            vendor.category,
            vendor.description,
            vendor.service_area,
            None,
            vendor.status,
        )
        _audit(request.user, AuditLog.ActionType.APPROVE_VENDOR, "vendor_profile", vendor.id)
        return Response({"id": str(vendor.id), "status": vendor.status})


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
        from tasks.marketplace_sync import delete_vendor_listing_from_fastapi

        delete_vendor_listing_from_fastapi(str(vendor.id))
        _audit(request.user, AuditLog.ActionType.REJECT_VENDOR, "vendor_profile", vendor.id, {"reason": reason})
        return Response({"id": str(vendor.id), "status": vendor.status, "rejection_reason": reason})


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
