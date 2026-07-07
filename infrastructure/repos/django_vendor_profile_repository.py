import logging
import uuid
from typing import Optional, List

from django.core.exceptions import ObjectDoesNotExist
from django.db import transaction

from domain.vendors.entities import VendorProfile as DomainProfile, VendorStatus, ServiceCategory
from domain.vendors.interfaces import IVendorProfileRepository
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
        return self.save(domain)

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

    def list_by_status(self, status: VendorStatus) -> List[DomainProfile]:
        objs = DjangoProfile.objects.filter(status=status.value).select_related("user")
        return [self._to_domain(o) for o in objs]

    def save(self, domain: DomainProfile) -> DomainProfile:
        try:
            obj = DjangoProfile.objects.get(id=domain.id)
        except DjangoProfile.DoesNotExist:
            obj = DjangoProfile(id=domain.id)

        obj.user = self._get_user(domain.user_id)
        obj.business_name = domain.business_name
        obj.category = domain.category.value
        obj.description = domain.description
        obj.service_area = domain.service_area
        obj.contact_email = domain.contact_email
        obj.contact_phone = domain.contact_phone
        obj.custom_category = domain.custom_category
        obj.website = domain.website
        obj.profile_image_url = domain.profile_image_url
        obj.profile_image_public_id = domain.profile_image_public_id
        obj.cover_image_url = domain.cover_image_url
        obj.cover_image_public_id = domain.cover_image_public_id
        obj.status = domain.status.value
        obj.submitted_at = domain.submitted_at
        obj.approved_at = domain.approved_at
        obj.rejected_at = domain.rejected_at
        obj.rejection_reason = domain.rejection_reason
        obj.save()
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
        return DomainProfile(
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
            created_at=model.created_at,
            updated_at=model.updated_at,
        )
