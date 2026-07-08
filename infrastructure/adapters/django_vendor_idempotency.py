from __future__ import annotations

from dataclasses import asdict, is_dataclass
from datetime import date, datetime
from decimal import Decimal
import uuid
from typing import Callable, TypeVar

from django.core.serializers.json import DjangoJSONEncoder
from django.db import IntegrityError, transaction
from django.utils import timezone
import json

from application.vendors.dtos import InquiryDTO, PortfolioImageDTO, ServicePackageDTO, VendorProfileDTO
from application.vendors.errors import VendorConflict
from django_app.vendors.models import VendorIdempotencyRecord

T = TypeVar("T")


class DjangoVendorIdempotencyAdapter:
    def execute_once(
        self,
        *,
        scope: str,
        actor_id: uuid.UUID,
        key: str,
        payload_fingerprint: str,
        operation: Callable[[], T],
    ) -> T:
        with transaction.atomic():
            record, created = self._reserve(scope, actor_id, key, payload_fingerprint)
            if record.status == VendorIdempotencyRecord.Status.COMPLETED:
                return self._deserialize_result(scope, record.result)
            if not created and record.status == VendorIdempotencyRecord.Status.IN_PROGRESS:
                raise VendorConflict(
                    "Idempotency key is already in progress.",
                    code="vendor_idempotency_in_progress",
                )
            try:
                result = operation()
            except Exception as exc:
                record.status = VendorIdempotencyRecord.Status.FAILED
                record.last_error = type(exc).__name__
                record.save(update_fields=["status", "last_error", "updated_at"])
                raise
            record.status = VendorIdempotencyRecord.Status.COMPLETED
            record.result = self._serialize_result(result)
            record.completed_at = timezone.now()
            record.last_error = None
            record.save(update_fields=["status", "result", "completed_at", "last_error", "updated_at"])
            return result

    def _reserve(self, scope: str, actor_id: uuid.UUID, key: str, fingerprint: str) -> tuple[VendorIdempotencyRecord, bool]:
        try:
            record, created = VendorIdempotencyRecord.objects.select_for_update().get_or_create(
                scope=scope,
                actor_id=actor_id,
                key=key,
                defaults={"payload_fingerprint": fingerprint},
            )
        except IntegrityError:
            record = VendorIdempotencyRecord.objects.select_for_update().get(scope=scope, actor_id=actor_id, key=key)
            created = False
        if not created and record.payload_fingerprint != fingerprint:
            raise VendorConflict(
                "Idempotency key was already used with a different payload.",
                code="vendor_idempotency_conflict",
            )
        if record.status == VendorIdempotencyRecord.Status.FAILED:
            record.status = VendorIdempotencyRecord.Status.IN_PROGRESS
            record.last_error = None
            record.save(update_fields=["status", "last_error", "updated_at"])
            created = True
        return record, created

    @staticmethod
    def _serialize_result(result) -> dict:
        payload = asdict(result) if is_dataclass(result) else result
        return json.loads(json.dumps(payload, cls=DjangoJSONEncoder))

    @staticmethod
    def _deserialize_result(scope: str, payload: dict):
        if scope == "vendor_profile.create":
            return VendorProfileDTO(
                id=uuid.UUID(payload["id"]),
                user_id=uuid.UUID(payload["user_id"]),
                business_name=payload["business_name"],
                category=payload["category"],
                description=payload["description"],
                service_area=payload["service_area"],
                contact_email=payload["contact_email"],
                contact_phone=payload["contact_phone"],
                custom_category=payload["custom_category"],
                website=payload["website"],
                profile_image_url=payload["profile_image_url"],
                cover_image_url=payload["cover_image_url"],
                status=payload["status"],
                submitted_at=_datetime(payload["submitted_at"]),
                approved_at=_datetime(payload["approved_at"]),
                rejected_at=_datetime(payload["rejected_at"]),
                rejection_reason=payload["rejection_reason"],
                version=payload["version"],
            )
        if scope == "portfolio_image.add":
            return PortfolioImageDTO(
                id=uuid.UUID(payload["id"]),
                vendor_id=uuid.UUID(payload["vendor_id"]),
                secure_url=payload["secure_url"],
                caption=payload["caption"],
                order=payload["order"],
                media_type=payload["media_type"],
                upload_status=payload["upload_status"],
                quality_status=payload["quality_status"],
                visibility_status=payload["visibility_status"],
                upload_error=payload["upload_error"],
                failure_reason=payload["failure_reason"],
                rejection_reason=payload["rejection_reason"],
                original_filename=payload["original_filename"],
                mime_type=payload["mime_type"],
                file_size=payload["file_size"],
                local_preview_url=payload["local_preview_url"],
                cloudinary_public_id=payload["cloudinary_public_id"],
                cloudinary_secure_url=payload["cloudinary_secure_url"],
                width=payload["width"],
                height=payload["height"],
                duration_seconds=payload["duration_seconds"],
                analyzer_score=payload["analyzer_score"],
                analyzer_summary=payload["analyzer_summary"],
                is_active=payload["is_active"],
                is_deleted=payload["is_deleted"],
                deleted_at=_datetime(payload["deleted_at"]),
                version=payload["version"],
            )
        if scope == "service_package.create":
            return ServicePackageDTO(
                id=uuid.UUID(payload["id"]),
                vendor_id=uuid.UUID(payload["vendor_id"]),
                name=payload["name"],
                description=payload["description"],
                price=Decimal(payload["price"]),
                currency=payload["currency"],
                package_tier=payload["package_tier"],
                approval_status=payload["approval_status"],
                rejection_reason=payload["rejection_reason"],
                is_active=payload["is_active"],
                is_deleted=payload["is_deleted"],
                deleted_at=_datetime(payload["deleted_at"]),
                version=payload["version"],
            )
        if scope == "vendor_inquiry.send":
            return InquiryDTO(
                id=uuid.UUID(payload["id"]),
                vendor_id=uuid.UUID(payload["vendor_id"]),
                client_name=payload["client_name"],
                client_email=payload["client_email"],
                client_phone=payload["client_phone"],
                message=payload["message"],
                event_date=_date(payload["event_date"]),
                is_read=payload["is_read"],
                created_at=_datetime(payload["created_at"]),
                version=payload["version"],
            )
        return payload


def _datetime(value: str | None) -> datetime | None:
    return datetime.fromisoformat(value) if value else None


def _date(value: str | None) -> date | None:
    return date.fromisoformat(value) if value else None
