import uuid
from typing import Optional, List
from django.core.exceptions import ObjectDoesNotExist

from domain.governance.entities import ContentFlag as DomainFlag, FlagStatus, ContentType
from domain.governance.interfaces import IContentFlagRepository
from django_app.governance.models import ContentFlag as DjangoFlag
from django_app.identity.models import User


class DjangoContentFlagRepository(IContentFlagRepository):
    def get_by_id(self, flag_id: uuid.UUID) -> Optional[DomainFlag]:
        try:
            obj = DjangoFlag.objects.select_related("reported_by").get(id=flag_id)
            return self._to_domain(obj)
        except ObjectDoesNotExist:
            return None

    def list_pending(self) -> List[DomainFlag]:
        objs = DjangoFlag.objects.filter(status=DjangoFlag.Status.PENDING).order_by("-created_at")
        return [self._to_domain(o) for o in objs]

    def list_by_content(self, content_type: ContentType, content_id: uuid.UUID) -> List[DomainFlag]:
        objs = DjangoFlag.objects.filter(
            content_type=content_type.value,
            content_id=content_id
        ).order_by("-created_at")
        return [self._to_domain(o) for o in objs]

    def save(self, domain_flag: DomainFlag) -> DomainFlag:
        try:
            obj = DjangoFlag.objects.get(id=domain_flag.id)
        except DjangoFlag.DoesNotExist:
            obj = DjangoFlag(id=domain_flag.id)

        obj.reported_by = User.objects.get(id=domain_flag.reported_by)
        obj.content_type = domain_flag.content_type.value
        obj.content_id = domain_flag.content_id
        obj.reason = domain_flag.reason
        obj.status = domain_flag.status.value
        obj.admin_notes = domain_flag.admin_notes
        obj.save()
        return self._to_domain(obj)

    def _to_domain(self, model: DjangoFlag) -> DomainFlag:
        return DomainFlag(
            id=model.id,
            reported_by=model.reported_by_id,
            content_type=ContentType(model.content_type),
            content_id=model.content_id,
            reason=model.reason,
            status=FlagStatus(model.status),
            admin_notes=model.admin_notes,
            created_at=model.created_at,
            updated_at=model.updated_at,
        )