import logging
import uuid
from typing import Optional

from django.core.exceptions import ObjectDoesNotExist
from django.db import transaction
from django.db.models import F

from domain.vendors.errors import ConcurrentVendorUpdate, VendorDomainError
from domain.vendors.entities import VendorProfile as DomainProfile, VendorStatus, ServiceCategory
from domain.vendors.interfaces import IVendorProfileRepository, Page, PageRequest
from django_app.vendors.models import VendorProfile as DjangoProfile
from django_app.identity.models import User
from django_app.governance.marketplace_outbox import enqueue_vendor_delete_projection, enqueue_vendor_projection
from infrastructure.repos.exceptions import RepositoryNotFoundError

logger = logging.getLogger(__name__)


def sync_or_delete_vendor_projection(vendor: DjangoProfile):
    return enqueue_vendor_projection(vendor, reason="vendor_repository_saved")


def delete_vendor_from_marketplace(vendor_id: uuid.UUID):
    return enqueue_vendor_delete_projection(vendor_id, reason="vendor_repository_deleted")


class DjangoVendorProfileRepository(IVendorProfileRepository):
    def add(self, domain: DomainProfile) -> DomainProfile:
        obj = DjangoProfile.objects.create(
            id=domain.id,
            user=self._get_user(domain.user_id),
            business_name=domain.business_name,
            category=domain.category.value,
            description=domain.description,
            service_area=domain.service_area,
            contact_email=domain.contact_email,
            contact_phone=domain.contact_phone,
            custom_category=domain.custom_category,
            website=domain.website,
            profile_image_url=domain.profile_image_url,
            profile_image_public_id=domain.profile_image_public_id,
            cover_image_url=domain.cover_image_url,
            cover_image_public_id=domain.cover_image_public_id,
            status=domain.status.value,
            submitted_at=domain.submitted_at,
            approved_at=domain.approved_at,
            rejected_at=domain.rejected_at,
            rejection_reason=domain.rejection_reason,
            version=domain.version,
            created_at=domain.created_at,
            updated_at=domain.updated_at,
        )
        saved = self._to_domain(obj)
        transaction.on_commit(lambda vendor_id=obj.id: self._enqueue_marketplace_projection(vendor_id))
        return saved

    def get_by_id(self, vendor_id: uuid.UUID) -> Optional[DomainProfile]:
        try:
            obj = DjangoProfile.objects.select_related("user").get(id=vendor_id)
            return self._to_domain(obj)
        except ObjectDoesNotExist:
            return None

    def get_by_user_id(self, user_id: uuid.UUID) -> Optional[DomainProfile]:
        try:
            obj = DjangoProfile.objects.select_related("user").get(user_id=user_id)
            return self._to_domain(obj)
        except ObjectDoesNotExist:
            return None

    def list_by_status(self, status: VendorStatus, page: PageRequest | None = None) -> Page[DomainProfile]:
        page = page or PageRequest()
        queryset = DjangoProfile.objects.filter(status=status.value).select_related("user").order_by("-created_at", "id")
        total = queryset.count()
        objs = list(queryset[page.offset : page.offset + page.limit])
        return Page(items=[self._to_domain(o) for o in objs], total=total, limit=page.limit, offset=page.offset)

    def save(self, domain: DomainProfile, *, expected_version: int) -> DomainProfile:
        self._get_user(domain.user_id)
        with transaction.atomic():
            updated = DjangoProfile.objects.filter(id=domain.id, version=expected_version).update(
                user_id=domain.user_id,
                business_name=domain.business_name,
                category=domain.category.value,
                description=domain.description,
                service_area=domain.service_area,
                contact_email=domain.contact_email,
                contact_phone=domain.contact_phone,
                custom_category=domain.custom_category,
                website=domain.website,
                profile_image_url=domain.profile_image_url,
                profile_image_public_id=domain.profile_image_public_id,
                cover_image_url=domain.cover_image_url,
                cover_image_public_id=domain.cover_image_public_id,
                status=domain.status.value,
                submitted_at=domain.submitted_at,
                approved_at=domain.approved_at,
                rejected_at=domain.rejected_at,
                rejection_reason=domain.rejection_reason,
                version=F("version") + 1,
                updated_at=domain.updated_at,
            )
            if updated == 0:
                raise ConcurrentVendorUpdate(
                    "Vendor profile was updated by another request.",
                    field_errors={"version": ["Vendor profile was updated by another request."]},
                )
            obj = DjangoProfile.objects.select_related("user").get(id=domain.id)
        saved = self._to_domain(obj)
        transaction.on_commit(lambda vendor_id=obj.id: self._enqueue_marketplace_projection(vendor_id))
        return saved

    def delete(self, vendor_id: uuid.UUID) -> None:
        DjangoProfile.objects.filter(id=vendor_id).delete()
        transaction.on_commit(lambda: self._enqueue_marketplace_delete(vendor_id))

    def _get_user(self, user_id: uuid.UUID):
        try:
            return User.objects.get(id=user_id)
        except User.DoesNotExist as exc:
            raise RepositoryNotFoundError("User not found") from exc

    def _enqueue_marketplace_projection(self, vendor_id: uuid.UUID) -> None:
        try:
            vendor = DjangoProfile.objects.get(id=vendor_id)
        except DjangoProfile.DoesNotExist:
            self._enqueue_marketplace_delete(vendor_id)
            return
        try:
            sync_or_delete_vendor_projection(vendor)
        except Exception:
            logger.exception("Vendor marketplace projection outbox enqueue failed.", extra={"vendor_id": str(vendor_id)})

    def _enqueue_marketplace_delete(self, vendor_id: uuid.UUID) -> None:
        try:
            delete_vendor_from_marketplace(vendor_id)
        except Exception:
            logger.exception("Vendor marketplace projection delete outbox enqueue failed.", extra={"vendor_id": str(vendor_id)})

    def _to_domain(self, model: DjangoProfile) -> DomainProfile:
        lifecycle_values = [value for value in (model.submitted_at, model.approved_at, model.rejected_at) if value]
        updated_at = model.updated_at
        if lifecycle_values and updated_at and max(lifecycle_values) > updated_at:
            updated_at = max(lifecycle_values)
        try:
            return DomainProfile.rehydrate(
                id=model.id,
                user_id=model.user_id,
                business_name=model.business_name,
                category=ServiceCategory(model.category),
                description=model.description,
                service_area=model.service_area,
                contact_email=model.contact_email,
                contact_phone=model.contact_phone,
                custom_category=model.custom_category,
                website=model.website,
                profile_image_url=model.profile_image_url,
                profile_image_public_id=model.profile_image_public_id,
                cover_image_url=model.cover_image_url,
                cover_image_public_id=model.cover_image_public_id,
                status=VendorStatus(model.status),
                submitted_at=model.submitted_at,
                approved_at=model.approved_at,
                rejected_at=model.rejected_at,
                rejection_reason=model.rejection_reason,
                version=model.version,
                created_at=model.created_at,
                updated_at=updated_at,
            )
        except VendorDomainError:
            logger.exception("VendorProfile strict hydration failed.", extra={"vendor_id": str(model.id)})
            raise
