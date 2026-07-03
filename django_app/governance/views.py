from datetime import timedelta
import logging

from django.conf import settings
from django.db.models import Prefetch, Q
from django.utils import timezone
from rest_framework.views import APIView
from rest_framework.response import Response
from rest_framework import status
from rest_framework.permissions import IsAuthenticated
from django_app.common.permissions import IsAdmin
from django_app.identity.models import PasswordResetEmailDelivery, User
from django_app.events.models import Event
from django_app.vendors.models import PortfolioImage, ServicePackage, VendorProfile, VerificationDocument
from domain.vendors.package_edit_policy import effective_next_edit_allowed_at
from .marketplace_outbox import enqueue_vendor_projection, enqueue_vendor_projection_by_id
from django_app.vendors.models import PortfolioImage, ServicePackage, VendorProfile
from .marketplace_outbox import enqueue_vendor_delete_projection, enqueue_vendor_projection, enqueue_vendor_projection_by_id
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
                "revenue": "0",
                "pending_vendor_approvals": VendorProfile.objects.filter(
                    status=VendorProfile.Status.PENDING_REVIEW
                ).count(),
            }
        )


class AdminEmailHealthView(APIView):
    permission_classes = [IsAuthenticated, IsAdmin]

    def get(self, request):
        recent_since = timezone.now() - timedelta(hours=24)
        failures = PasswordResetEmailDelivery.objects.filter(
            status=PasswordResetEmailDelivery.Status.FAILED,
            updated_at__gte=recent_since,
        ).count()
        deferred = PasswordResetEmailDelivery.objects.filter(
            status=PasswordResetEmailDelivery.Status.DEFERRED,
            updated_at__gte=recent_since,
        ).count()
        last_success = (
            PasswordResetEmailDelivery.objects.filter(status=PasswordResetEmailDelivery.Status.SENT)
            .order_by("-sent_at")
            .first()
        )
        last_failure = (
            PasswordResetEmailDelivery.objects.filter(
                status__in=[
                    PasswordResetEmailDelivery.Status.FAILED,
                    PasswordResetEmailDelivery.Status.DEFERRED,
                ]
            )
            .order_by("-failed_at")
            .first()
        )
        email_backend_configured = bool((getattr(settings, "EMAIL_BACKEND", "") or "").strip())
        default_from_email_configured = bool((getattr(settings, "DEFAULT_FROM_EMAIL", "") or "").strip())
        frontend_url_configured = bool((getattr(settings, "FRONTEND_URL", "") or "").strip())

        status_value = "healthy"
        if not all([email_backend_configured, default_from_email_configured, frontend_url_configured]):
            status_value = "unhealthy"
        elif failures or deferred:
            status_value = "degraded"

        if status_value == "unhealthy":
            logger.error(
                "email_health_unhealthy",
                extra={
                    "email_backend_configured": email_backend_configured,
                    "default_from_email_configured": default_from_email_configured,
                    "frontend_url_configured": frontend_url_configured,
                },
            )

        return Response(
            {
                "status": status_value,
                "email_backend_configured": email_backend_configured,
                "default_from_email_configured": default_from_email_configured,
                "frontend_url_configured": frontend_url_configured,
                "recent_password_reset_email_failures": failures,
                "recent_password_reset_email_deferred": deferred,
                "last_success_at": last_success.sent_at.isoformat() if last_success and last_success.sent_at else None,
                "last_failure_at": last_failure.failed_at.isoformat() if last_failure and last_failure.failed_at else None,
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
        "custom_category": vendor.custom_category,
        "description": vendor.description,
        "service_area": vendor.service_area,
        "contact_email": vendor.contact_email,
        "contact_phone": vendor.contact_phone,
        "website": vendor.website,
        "profile_image_url": vendor.profile_image_url,
        "cover_image_url": vendor.cover_image_url,
        "status": vendor.status,
        "submitted_at": vendor.submitted_at.isoformat() if vendor.submitted_at else None,
        "approved_at": vendor.approved_at.isoformat() if vendor.approved_at else None,
        "rejected_at": vendor.rejected_at.isoformat() if vendor.rejected_at else None,
        "rejection_reason": vendor.rejection_reason,
        "created_at": vendor.created_at.isoformat(),
        "updated_at": vendor.updated_at.isoformat(),
    }


def _admin_action_success(payload: dict, *, code: str, message: str) -> dict:
    response_data = dict(payload)
    data = dict(payload)
    response_data.setdefault("success", True)
    response_data.setdefault("code", code)
    response_data.setdefault("message", message)
    response_data.setdefault("data", data)
    return response_data


def _admin_action_error(code: str, message: str, response_status: int) -> Response:
    return Response(
        {
            "success": False,
            "code": code,
            "message": message,
            "detail": message,
            "field_errors": {},
        },
        status=response_status,
    )


def _serialize_admin_vendor_detail(vendor: VendorProfile) -> dict:
    user = getattr(vendor, "user", None)
    packages = list(getattr(vendor, "admin_packages", vendor.packages.all()))
    portfolio = list(getattr(vendor, "admin_portfolio", vendor.images.all()))
    documents = list(vendor.verification_documents.all())
    package_ids = [package.id for package in packages]
    portfolio_ids = [item.id for item in portfolio]
    audit_logs = (
        AuditLog.objects.select_related("admin")
        .filter(
            Q(target_type="vendor_profile", target_id=vendor.id)
            | Q(target_type="service_package", target_id__in=package_ids)
            | Q(target_type="portfolio_image", target_id__in=portfolio_ids)
        )
        .order_by("-created_at")[:20]
    )
    data = {
        "profile": _serialize_vendor(vendor),
        "user": _serialize_user(user) if user else None,
        "packages": [_serialize_admin_package(package) for package in packages],
        "portfolio": [_serialize_admin_portfolio_media(item) for item in portfolio],
        "verification_documents": [_serialize_verification_document(document) for document in documents],
        "review_context": _admin_vendor_review_context(packages, portfolio, documents),
        "available_actions": _admin_vendor_available_actions(vendor, user),
        "audit_logs": [_serialize_audit_log(log, include_admin_detail=True) for log in audit_logs],
    }
    return {
        "success": True,
        "code": "admin_vendor_detail_loaded",
        "message": "Vendor review detail loaded.",
        "data": data,
    }


def _serialize_admin_package(package: ServicePackage) -> dict:
    next_allowed = effective_next_edit_allowed_at(package)
    now = timezone.now()
    return {
        "id": str(package.id),
        "vendor_id": str(package.vendor_id),
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
        "last_approved_at": package.last_approved_at.isoformat() if package.last_approved_at else None,
        "last_vendor_public_edit_at": (
            package.last_vendor_public_edit_at.isoformat() if package.last_vendor_public_edit_at else None
        ),
        "next_vendor_edit_allowed_at": next_allowed.isoformat() if next_allowed else None,
        "can_edit_now": next_allowed is None or now >= next_allowed,
        "created_at": package.created_at.isoformat(),
        "updated_at": package.updated_at.isoformat(),
    }


def _serialize_admin_portfolio_media(media: PortfolioImage) -> dict:
    display_url = media.cloudinary_secure_url or media.secure_url or media.local_preview_url
    return {
        "id": str(media.id),
        "vendor_id": str(media.vendor_id),
        "media_type": media.media_type,
        "secure_url": media.cloudinary_secure_url or media.secure_url,
        "display_url": display_url,
        "local_preview_url": media.local_preview_url,
        "caption": media.caption,
        "order": media.order,
        "upload_status": media.upload_status,
        "quality_status": media.quality_status,
        "visibility_status": media.visibility_status,
        "rejection_reason": media.rejection_reason,
        "failure_reason": media.failure_reason,
        "analyzer_score": media.analyzer_score,
        "analyzer_summary": media.analyzer_summary,
        "width": media.width,
        "height": media.height,
        "duration_seconds": media.duration_seconds,
        "is_active": media.is_active,
        "is_deleted": media.is_deleted,
        "created_at": media.created_at.isoformat(),
        "updated_at": media.updated_at.isoformat(),
    }


def _serialize_verification_document(document: VerificationDocument) -> dict:
    return {
        "id": str(document.id),
        "document_type": document.document_type,
        "original_filename": document.original_filename,
        "secure_url": document.secure_url,
        "cloudinary_secure_url": document.cloudinary_secure_url,
        "mime_type": document.mime_type,
        "file_size": document.file_size,
        "upload_status": document.upload_status,
        "verification_status": document.verification_status,
        "failure_reason": document.failure_reason,
        "fraud_status": document.fraud_status,
        "fraud_score": document.fraud_score,
        "fraud_reasons": document.fraud_reasons,
        "odcr_status": document.odcr_status,
        "odcr_score": document.odcr_score,
        "odcr_result_summary": document.odcr_result_summary,
        "created_at": document.created_at.isoformat(),
        "updated_at": document.updated_at.isoformat(),
    }


def _admin_vendor_review_context(
    packages: list[ServicePackage],
    portfolio: list[PortfolioImage],
    documents: list[VerificationDocument],
) -> dict:
    return {
        "packages_count": len(packages),
        "pending_packages_count": sum(
            1 for package in packages if package.approval_status == ServicePackage.ApprovalStatus.WAITING_APPROVAL
        ),
        "approved_packages_count": sum(
            1 for package in packages if package.approval_status == ServicePackage.ApprovalStatus.APPROVED
        ),
        "rejected_packages_count": sum(
            1 for package in packages if package.approval_status == ServicePackage.ApprovalStatus.REJECTED
        ),
        "portfolio_count": len(portfolio),
        "pending_portfolio_count": sum(
            1 for item in portfolio if item.visibility_status == PortfolioImage.VisibilityStatus.WAITING_APPROVAL
        ),
        "approved_portfolio_count": sum(
            1 for item in portfolio if item.visibility_status == PortfolioImage.VisibilityStatus.APPROVED
        ),
        "rejected_portfolio_count": sum(
            1 for item in portfolio if item.visibility_status == PortfolioImage.VisibilityStatus.REJECTED
        ),
        "verification_documents_count": len(documents),
        "verified_documents_count": sum(
            1 for document in documents if document.verification_status == VerificationDocument.VerificationStatus.VERIFIED
        ),
        "failed_documents_count": sum(
            1
            for document in documents
            if document.verification_status
            in {VerificationDocument.VerificationStatus.FAILED, VerificationDocument.VerificationStatus.REJECTED}
        ),
    }


def _admin_vendor_available_actions(vendor: VendorProfile, user: User | None) -> dict:
    return {
        "approve_vendor": vendor.status == VendorProfile.Status.PENDING_REVIEW,
        "reject_vendor": vendor.status == VendorProfile.Status.PENDING_REVIEW,
        "suspend_vendor": vendor.status == VendorProfile.Status.APPROVED,
        "reinstate_vendor": vendor.status == VendorProfile.Status.SUSPENDED,
        "ban_user": bool(user and user.is_active),
        "reinstate_user": bool(user and not user.is_active),
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


def _serialize_portfolio_media(media: PortfolioImage) -> dict:
    return {
        "id": str(media.id),
        "vendor_id": str(media.vendor_id),
        "vendor_business_name": media.vendor.business_name,
        "media_type": media.media_type,
        "secure_url": media.cloudinary_secure_url or media.secure_url,
        "local_preview_url": media.local_preview_url,
        "caption": media.caption,
        "order": media.order,
        "upload_status": media.upload_status,
        "quality_status": media.quality_status,
        "visibility_status": media.visibility_status,
        "rejection_reason": media.rejection_reason,
        "failure_reason": media.failure_reason,
        "analyzer_score": media.analyzer_score,
        "analyzer_summary": media.analyzer_summary,
        "is_active": media.is_active,
        "is_deleted": media.is_deleted,
        "created_at": media.created_at.isoformat(),
        "updated_at": media.updated_at.isoformat(),
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


def _serialize_audit_log(log: AuditLog, *, include_admin_detail: bool = False) -> dict:
    payload = {
        "id": str(log.id),
        "admin": str(log.admin_id) if log.admin_id else None,
        "action_type": log.action_type,
        "target_type": log.target_type,
        "target_id": str(log.target_id),
        "details": log.details,
        "created_at": log.created_at.isoformat(),
    }
    if include_admin_detail:
        payload["admin"] = _serialize_user(log.admin) if log.admin else None
    return payload


def _audit(admin, action_type: str, target_type: str, target_id, details: dict | None = None) -> None:
    AuditLog.objects.create(
        admin=admin,
        action_type=action_type,
        target_type=target_type,
        target_id=target_id,
        details=details or {},
    )


def sync_vendor_to_marketplace(vendor: VendorProfile):
    return enqueue_vendor_projection(vendor, reason="vendor_approved")


def delete_vendor_from_marketplace(vendor_id):
    return enqueue_vendor_delete_projection(vendor_id, reason="vendor_removed_from_marketplace")


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


class AdminVendorDetailView(APIView):
    permission_classes = [IsAuthenticated, IsAdmin]

    def get(self, request, vendor_id):
        try:
            vendor = (
                VendorProfile.objects.select_related("user")
                .prefetch_related(
                    Prefetch(
                        "packages",
                        queryset=ServicePackage.all_objects.order_by("-updated_at", "-created_at"),
                        to_attr="admin_packages",
                    ),
                    Prefetch(
                        "images",
                        queryset=PortfolioImage.all_objects.order_by("order", "-updated_at", "-created_at"),
                        to_attr="admin_portfolio",
                    ),
                    "verification_documents",
                )
                .get(id=vendor_id)
            )
        except VendorProfile.DoesNotExist:
            return Response({"detail": "Vendor not found."}, status=status.HTTP_404_NOT_FOUND)

        return Response(_serialize_admin_vendor_detail(vendor))


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
            return _admin_action_error("vendor_approve_failed", "Vendor not found.", status.HTTP_404_NOT_FOUND)
        if vendor.status != VendorProfile.Status.PENDING_REVIEW:
            return _admin_action_error(
                "vendor_approve_failed",
                "Vendor must be submitted for review before approval.",
                status.HTTP_400_BAD_REQUEST,
            )

        from django.utils import timezone

        vendor.status = VendorProfile.Status.APPROVED
        vendor.approved_at = timezone.now()
        vendor.rejected_at = None
        vendor.rejection_reason = None
        vendor.save(update_fields=["status", "approved_at", "rejected_at", "rejection_reason", "updated_at"])
        _sync_approved_vendor(vendor)
        _audit(request.user, AuditLog.ActionType.APPROVE_VENDOR, "vendor_profile", vendor.id)
        return Response(
            _admin_action_success(
                _serialize_vendor(vendor),
                code="vendor_approve_completed",
                message="Vendor approved successfully.",
            )
        )


class AdminVendorRejectView(APIView):
    permission_classes = [IsAuthenticated, IsAdmin]

    def post(self, request, vendor_id):
        reason = request.data.get("reason") or "Rejected by administrator."
        try:
            vendor = VendorProfile.objects.get(id=vendor_id)
        except VendorProfile.DoesNotExist:
            return _admin_action_error("vendor_reject_failed", "Vendor not found.", status.HTTP_404_NOT_FOUND)
        if vendor.status != VendorProfile.Status.PENDING_REVIEW:
            return _admin_action_error(
                "vendor_reject_failed",
                "Only vendors waiting for review can be rejected.",
                status.HTTP_400_BAD_REQUEST,
            )

        from django.utils import timezone

        vendor.status = VendorProfile.Status.REJECTED
        vendor.rejected_at = timezone.now()
        vendor.rejection_reason = reason
        vendor.save(update_fields=["status", "rejected_at", "rejection_reason", "updated_at"])
        _delete_vendor_listing(vendor)
        _audit(request.user, AuditLog.ActionType.REJECT_VENDOR, "vendor_profile", vendor.id, {"reason": reason})
        return Response(
            _admin_action_success(
                _serialize_vendor(vendor),
                code="vendor_reject_completed",
                message="Vendor rejected successfully.",
            )
        )


class AdminVendorSuspendView(APIView):
    permission_classes = [IsAuthenticated, IsAdmin]

    def post(self, request, vendor_id):
        try:
            vendor = VendorProfile.objects.get(id=vendor_id)
        except VendorProfile.DoesNotExist:
            return _admin_action_error("vendor_suspend_failed", "Vendor not found.", status.HTTP_404_NOT_FOUND)
        if vendor.status != VendorProfile.Status.APPROVED:
            return _admin_action_error(
                "vendor_suspend_failed",
                "Only approved vendors can be suspended.",
                status.HTTP_400_BAD_REQUEST,
            )

        vendor.status = VendorProfile.Status.SUSPENDED
        vendor.save(update_fields=["status", "updated_at"])
        _delete_vendor_listing(vendor)
        _audit(request.user, AuditLog.ActionType.SUSPEND_VENDOR, "vendor_profile", vendor.id)
        return Response(
            _admin_action_success(
                _serialize_vendor(vendor),
                code="vendor_suspend_completed",
                message="Vendor suspended successfully.",
            )
        )


class AdminVendorReinstateView(APIView):
    permission_classes = [IsAuthenticated, IsAdmin]

    def post(self, request, vendor_id):
        try:
            vendor = VendorProfile.objects.get(id=vendor_id)
        except VendorProfile.DoesNotExist:
            return _admin_action_error("vendor_reinstate_failed", "Vendor not found.", status.HTTP_404_NOT_FOUND)
        if vendor.status != VendorProfile.Status.SUSPENDED:
            return _admin_action_error(
                "vendor_reinstate_failed",
                "Only suspended vendors can be reinstated.",
                status.HTTP_400_BAD_REQUEST,
            )

        from django.utils import timezone

        vendor.status = VendorProfile.Status.APPROVED
        vendor.approved_at = timezone.now()
        vendor.save(update_fields=["status", "approved_at", "updated_at"])
        _sync_approved_vendor(vendor)
        _audit(request.user, AuditLog.ActionType.APPROVE_VENDOR, "vendor_profile", vendor.id, {"from": "suspended"})
        return Response(
            _admin_action_success(
                _serialize_vendor(vendor),
                code="vendor_reinstate_completed",
                message="Vendor reinstated successfully.",
            )
        )


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
        enqueue_vendor_projection(package.vendor, reason="package_approved")
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
        enqueue_vendor_projection(package.vendor, reason="package_rejected")
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
        vendor = package.vendor
        _audit(request.user, AuditLog.ActionType.HARD_DELETE_PACKAGE, "service_package", package_id_value)
        package.hard_delete()
        enqueue_vendor_projection(vendor, reason="package_hard_deleted")
        return Response({"message": "Package permanently deleted.", "package_id": str(package_id_value)})


class AdminVendorPortfolioPendingListView(APIView):
    permission_classes = [IsAuthenticated, IsAdmin]

    def get(self, request):
        media = (
            PortfolioImage.objects.select_related("vendor")
            .filter(
                visibility_status__in=[
                    PortfolioImage.VisibilityStatus.PRIVATE,
                    PortfolioImage.VisibilityStatus.WAITING_APPROVAL,
                ],
                upload_status=PortfolioImage.UploadStatus.UPLOADED,
            )
            .exclude(quality_status=PortfolioImage.QualityStatus.FAILED)
            .order_by("-updated_at", "-created_at")
        )
        return Response({"results": [_serialize_portfolio_media(item) for item in media], "count": media.count()})


class AdminVendorPortfolioApproveView(APIView):
    permission_classes = [IsAuthenticated, IsAdmin]

    def post(self, request, media_id):
        try:
            media = PortfolioImage.objects.select_related("vendor").get(id=media_id)
        except PortfolioImage.DoesNotExist:
            return Response({"detail": "Portfolio item not found."}, status=status.HTTP_404_NOT_FOUND)

        if media.upload_status != PortfolioImage.UploadStatus.UPLOADED:
            return Response(
                {"detail": "Portfolio item must finish uploading before approval."},
                status=status.HTTP_400_BAD_REQUEST,
            )
        if media.quality_status == PortfolioImage.QualityStatus.FAILED:
            return Response(
                {"detail": "Portfolio item failed quality review and cannot be approved."},
                status=status.HTTP_400_BAD_REQUEST,
            )

        media.visibility_status = PortfolioImage.VisibilityStatus.APPROVED
        media.rejection_reason = None
        media.is_active = True
        media.save(update_fields=["visibility_status", "rejection_reason", "is_active", "updated_at"])
        _audit(request.user, AuditLog.ActionType.APPROVE_PORTFOLIO_MEDIA, "portfolio_image", media.id)
        return Response({"message": "Portfolio item approved.", "portfolio_item": _serialize_portfolio_media(media)})


class AdminVendorPortfolioRejectView(APIView):
    permission_classes = [IsAuthenticated, IsAdmin]

    def post(self, request, media_id):
        reason = request.data.get("reason") or "Portfolio item rejected by administrator."
        try:
            media = PortfolioImage.objects.select_related("vendor").get(id=media_id)
        except PortfolioImage.DoesNotExist:
            return Response({"detail": "Portfolio item not found."}, status=status.HTTP_404_NOT_FOUND)

        media.visibility_status = PortfolioImage.VisibilityStatus.REJECTED
        media.rejection_reason = reason
        media.is_active = False
        media.save(update_fields=["visibility_status", "rejection_reason", "is_active", "updated_at"])
        _audit(request.user, AuditLog.ActionType.REJECT_PORTFOLIO_MEDIA, "portfolio_image", media.id, {"reason": reason})
        return Response({"message": "Portfolio item rejected.", "portfolio_item": _serialize_portfolio_media(media)})


class AdminVendorPortfolioHardDeleteView(APIView):
    permission_classes = [IsAuthenticated, IsAdmin]

    def delete(self, request, media_id):
        try:
            media = PortfolioImage.all_objects.select_related("vendor").get(id=media_id)
        except PortfolioImage.DoesNotExist:
            return Response({"detail": "Portfolio item not found."}, status=status.HTTP_404_NOT_FOUND)

        media_id_value = media.id
        _audit(request.user, AuditLog.ActionType.HARD_DELETE_PORTFOLIO_MEDIA, "portfolio_image", media_id_value)
        media.hard_delete()
        return Response({"message": "Portfolio item permanently deleted.", "portfolio_item_id": str(media_id_value)})


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
