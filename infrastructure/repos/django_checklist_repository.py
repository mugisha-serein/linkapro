import uuid
from typing import Optional, List
from django.core.exceptions import ObjectDoesNotExist

from domain.events.entities import Checklist as DomainChecklist
from domain.events.interfaces import IChecklistRepository
from django_app.events.models import Checklist as DjangoChecklist, Event as DjangoEvent


class DjangoChecklistRepository(IChecklistRepository):
    def get_by_id(self, checklist_id: uuid.UUID) -> Optional[DomainChecklist]:
        try:
            obj = DjangoChecklist.objects.get(id=checklist_id)
            return self._to_domain(obj)
        except ObjectDoesNotExist:
            return None

    def list_by_event(self, event_id: uuid.UUID) -> List[DomainChecklist]:
        objs = DjangoChecklist.objects.filter(event_id=event_id)
        return [self._to_domain(o) for o in objs]

    def save(self, domain: DomainChecklist) -> DomainChecklist:
        try:
            obj = DjangoChecklist.objects.get(id=domain.id)
        except DjangoChecklist.DoesNotExist:
            obj = DjangoChecklist(id=domain.id)
        obj.event = DjangoEvent.objects.get(id=domain.event_id)
        obj.name = domain.name
        obj.save()
        return self._to_domain(obj)

    def delete(self, checklist_id: uuid.UUID) -> None:
        DjangoChecklist.objects.filter(id=checklist_id).delete()

    def _to_domain(self, model: DjangoChecklist) -> DomainChecklist:
        return DomainChecklist(
            id=model.id,
            event_id=model.event_id,
            name=model.name,
            created_at=model.created_at,
            updated_at=model.updated_at,
        )