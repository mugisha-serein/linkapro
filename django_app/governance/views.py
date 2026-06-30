from datetime import timedelta
import logging

from django.conf import settings
from django.utils import timezone
from rest_framework.views import APIView
from rest_framework.response import Response
from rest_framework import status
from rest_framework.permissions import IsAuthenticated
from django_app.common.permissions import IsAdmin
from django_app.identity.models import PasswordResetEmailDelivery, User
from django_app.events.models import Event
from django_app.vendors.models import PortfolioImage, ServicePackage, VendorProfile
from .marketplace_outbox import enqueue_vendor_projection
from .models import AuditLog, ContentFlag
from .serializers import FlagContentSerializer
from .services import get_command_handlers, get_query_handlers
from application.governance.commands import FlagContentCommand

VENDOR_ADMIN_STATUSES = {choice[0] for choice in VendorProfile.Status.choices}
logger = logging.getLogger(__name__)


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
                "pending_vendor_approvals": VendorProfile.objects.filter(
                    status=VendorProfile.Status.PENDING_REVIEW
                ).count(),
                "revenue": "0",
            }
        )


def _vendor_status_counts() -> dict:
    return {
        status_value: VendorProfile.objects.filter(status=status_value).count()
        for status_value in VENDOR_ADMIN_STATUSES
    }


def _serialize_user(user: User) -> dict:
    return {
        "id": str(user.id),
        "email": user.email,
        "full_name": user.full_name,
        "role": user.role,
        "is_active": user.is_active,
        "created_at": user.created_at.isoformat() if user.created_at else None,
        "last_login": user.last_login.isoformat() if user.last_login else None,
    }


def _serialize_vendor(vendor: VendorProfile) -> dict:
    return {
        "id": str(vendor.id),
        "user_id": str(vendor.user_id),
        "business_name": vendor.business_name,
        "category": vendor.category,
        "custom_category": vendor.custom_category,
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
        "created_at": vendor.created_at.isoformat() if vendor.created_at else None,
        "updated_at": vendor.updated_at.isoformat() if vendor.updated_at else None,
        "profile_complete": vendor.is_profile_complete,
    }


def _serialize_package(package: ServicePackage) -> dict:
    return {
        "id": str(package.id),
        "vendor_id": str(package.vendor_id),
        "vendor_name": package.vendor.business_name,
        "name": package.name,
        "description": package.description,
        "price": str(package.price),
        "currency": package.currency,
        "package_tier": package.package_tier,
        "approval_status": package.approval_status,
        "rejection_reason": package.rejection_reason,
        "is_active": package.is_active,
        "created_at": package.created_at.isoformat() if package.created_at else None,
        "updated_at": package.updated_at.isoformat() if package.updated_at else None,
    }


def _serialize_portfolio_media(media: PortfolioImage) -> dict:
    return {
        "id": str(media.id),
        "vendor_id": str(media.vendor_id),
        "vendor_name": media.vendor.business_name,
        "media_type": media.media_type,
        "secure_url": media.secure_url,
        "display_url": media.cloudinary_secure_url or media.secure_url or media.local_preview_url,
        "caption": media.caption,
        "upload_status": media.upload_status,
        "quality_status": media.quality_status,
        "visibility_status": media.visibility_status,
        "rejection_reason": media.rejection_reason,
        "created_at": media.created_at.isoformat() if media.created_at else None,
        "updated_at": media.updated_at.isoformat() if media.updated_at else None,
    }


def _serialize_flag(flag: ContentFlag) -> dict:
    return {
        "id": str(flag.id),
        "reported_by": str(flag.reported_by_id),
        "content_type": flag.content_type,
        "content_id": str(flag.content_id),
        "reason": flag.reason,
        "status": flag.status,
        "admin_notes": flag.admin_notes,
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
    enqueue_vendor_projection(vendor, reason="vendor_approved")


def _delete_vendor_listing(vendor: VendorProfile) -> None:
    enqueue_vendor_projection(vendor, reason="vendor_removed_from_marketplace")


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


# Remaining admin views are intentionally unchanged below this file in the next patch.
