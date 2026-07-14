from __future__ import annotations

from datetime import timedelta
import uuid

from django.conf import settings
from django.db import IntegrityError, transaction
from django.utils import timezone

from application.vendors.shared.commands import AuthenticatedActor, ModeratorActor
from application.vendors.errors import (
    InquiryAbuseDenied,
    VendorOperationForbidden,
    VendorResourceNotFound,
)
from application.vendors.inquiries.ports import InquiryAbuseProtectionPort
from application.vendors.shared.ports import VendorAuthorizationPort
from django_app.identity.models import User

from .abuse_models import InquiryAbuseRecord
from .models import VendorProfile


class DjangoVendorAuthorizationAdapter(VendorAuthorizationPort):
    """Resolve vendor ownership and moderator authority from persisted identity data."""

    def assert_actor_owns_vendor(self, actor: AuthenticatedActor, vendor_id: uuid.UUID) -> None:
        if VendorProfile.objects.filter(id=vendor_id, user_id=actor.user_id).exists():
            return
        if not VendorProfile.objects.filter(id=vendor_id).exists():
            raise VendorResourceNotFound("Vendor not found.")
        raise VendorOperationForbidden("You do not own this vendor profile.")

    def assert_actor_can_access_vendor(self, actor: AuthenticatedActor, vendor_id: uuid.UUID) -> None:
        if VendorProfile.objects.filter(id=vendor_id, user_id=actor.user_id).exists():
            return
        is_admin = User.objects.filter(
            id=actor.user_id,
            is_active=True,
            role=User.Role.ADMIN,
        ).exists()
        if is_admin and VendorProfile.objects.filter(id=vendor_id).exists():
            return
        if not VendorProfile.objects.filter(id=vendor_id).exists():
            raise VendorResourceNotFound("Vendor not found.")
        raise VendorOperationForbidden("Vendor access is not allowed.")

    def assert_moderator_can_moderate_vendor(self, moderator: ModeratorActor, vendor_id: uuid.UUID) -> None:
        authorized = User.objects.filter(
            id=moderator.user_id,
            is_active=True,
            role=User.Role.ADMIN,
        ).exists()
        if not authorized:
            raise VendorOperationForbidden("Vendor moderation is not allowed.")
        if not VendorProfile.objects.filter(id=vendor_id).exists():
            raise VendorResourceNotFound("Vendor not found.")


class DjangoInquiryAbuseProtectionAdapter(InquiryAbuseProtectionPort):
    """Serialize public inquiry admission and durably reject duplicate bursts."""

    def assert_inquiry_allowed(
        self,
        *,
        requester_identity: uuid.UUID,
        vendor_id: uuid.UUID,
        payload_digest: str,
    ) -> None:
        duplicate_window_seconds = int(
            getattr(settings, "VENDOR_INQUIRY_DUPLICATE_WINDOW_SECONDS", 600)
        )
        rate_window_seconds = int(
            getattr(settings, "VENDOR_INQUIRY_RATE_WINDOW_SECONDS", 3600)
        )
        max_requests = int(getattr(settings, "VENDOR_INQUIRY_MAX_REQUESTS_PER_WINDOW", 5))
        now = timezone.now()
        duplicate_cutoff = now - timedelta(seconds=duplicate_window_seconds)
        rate_cutoff = now - timedelta(seconds=rate_window_seconds)

        with transaction.atomic():
            try:
                VendorProfile.objects.select_for_update().get(id=vendor_id)
            except VendorProfile.DoesNotExist as exc:
                raise VendorResourceNotFound("Vendor not found.") from exc

            recent = InquiryAbuseRecord.objects.filter(
                requester_identity=requester_identity,
                vendor_id=vendor_id,
                created_at__gte=rate_cutoff,
            )
            if recent.count() >= max_requests:
                raise InquiryAbuseDenied("Too many inquiry attempts. Please try again later.")
            if recent.filter(
                payload_digest=payload_digest,
                created_at__gte=duplicate_cutoff,
            ).exists():
                raise InquiryAbuseDenied("This inquiry was already submitted recently.")

            try:
                InquiryAbuseRecord.objects.create(
                    requester_identity=requester_identity,
                    vendor_id=vendor_id,
                    payload_digest=payload_digest,
                    duplicate_window_key=self._window_key(now, duplicate_window_seconds),
                )
            except IntegrityError as exc:
                raise InquiryAbuseDenied("This inquiry was already submitted recently.") from exc

    @staticmethod
    def _window_key(now, window_seconds: int) -> int:
        timestamp = int(now.timestamp())
        return timestamp - (timestamp % max(window_seconds, 1))
