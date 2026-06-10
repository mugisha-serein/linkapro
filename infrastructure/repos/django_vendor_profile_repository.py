import uuid
import logging
from typing import Optional, List
from django.core.exceptions import ObjectDoesNotExist

from domain.vendors.entities import VendorProfile as DomainProfile, VendorStatus, ServiceCategory
from domain.vendors.interfaces import IVendorProfileRepository
from django_app.vendors.models import VendorProfile as DjangoProfile
from django_app.identity.models import User

logger = logging.getLogger(__name__)


class DjangoVendorProfileRepository(IVendorProfileRepository):
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

        obj.user = User.objects.get(id=domain.user_id)
        obj.business_name = domain.business_name
        obj.category = domain.category.value
        obj.description = domain.description
        obj.service_area = domain.service_area
        obj.contact_email = domain.contact_email
        obj.contact_phone = domain.contact_phone
        obj.website = domain.website
        obj.status = domain.status.value
        obj.submitted_at = domain.submitted_at
        obj.approved_at = domain.approved_at
        obj.rejected_at = domain.rejected_at
        obj.rejection_reason = domain.rejection_reason
        obj.save()
        if obj.status == DjangoProfile.Status.APPROVED:
            self._sync_marketplace_projection(obj)
        else:
            self._delete_marketplace_projection(obj.id)
        return self._to_domain(obj)

    def delete(self, vendor_id: uuid.UUID) -> None:
        DjangoProfile.objects.filter(id=vendor_id).delete()
        self._delete_marketplace_projection(vendor_id)

    def _sync_marketplace_projection(self, obj: DjangoProfile) -> None:
        from tasks.marketplace_sync import sync_vendor_listing_to_fastapi

        try:
            sync_vendor_listing_to_fastapi(
                str(obj.id),
                obj.business_name,
                obj.category,
                obj.description,
                obj.service_area,
                None,
                obj.status,
            )
        except Exception:
            logger.exception(
                "Failed to sync vendor profile to FastAPI marketplace",
                extra={"vendor_id": str(obj.id)},
            )
            raise

    def _delete_marketplace_projection(self, vendor_id: uuid.UUID) -> None:
        from tasks.marketplace_sync import delete_vendor_listing_from_fastapi

        try:
            delete_vendor_listing_from_fastapi(str(vendor_id))
        except Exception:
            logger.exception(
                "Failed to delete vendor projection from FastAPI marketplace",
                extra={"vendor_id": str(vendor_id)},
            )
            raise

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
            website=model.website,
            status=VendorStatus(model.status),
            submitted_at=model.submitted_at,
            approved_at=model.approved_at,
            rejected_at=model.rejected_at,
            rejection_reason=model.rejection_reason,
            created_at=model.created_at,
            updated_at=model.updated_at,
        )
