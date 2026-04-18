import uuid
from typing import Optional, List
from django.core.exceptions import ObjectDoesNotExist

from domain.events.entities import ChecklistItem as DomainItem, ChecklistItemStatus
from domain.events.interfaces import IChecklistItemRepository
from django_app.events.models import ChecklistItem as DjangoItem, Checklist as DjangoChecklist


class DjangoChecklistItemRepository(IChecklistItemRepository):
    def get_by_id(self, item_id: uuid.UUID) -> Optional[DomainItem]:
        try:
            obj = DjangoItem.objects.select_related("checklist").get(id=item_id)
            return self._to_domain(obj)
        except ObjectDoesNotExist:
            return None

    def list_by_checklist(self, checklist_id: uuid.UUID) -> List[DomainItem]:
        objs = DjangoItem.objects.filter(checklist_id=checklist_id).order_by("order")
        return [self._to_domain(o) for o in objs]

    def save(self, domain_item: DomainItem) -> DomainItem:
        try:
            obj = DjangoItem.objects.get(id=domain_item.id)
        except DjangoItem.DoesNotExist:
            obj = DjangoItem(id=domain_item.id)

        obj.checklist = DjangoChecklist.objects.get(id=domain_item.checklist_id)
        obj.description = domain_item.description
        obj.status = domain_item.status.value
        obj.due_date = domain_item.due_date
        obj.assigned_to = domain_item.assigned_to
        obj.order = domain_item.order
        obj.save()
        return self._to_domain(obj)

    def delete(self, item_id: uuid.UUID) -> None:
        DjangoItem.objects.filter(id=item_id).delete()

    def _to_domain(self, model: DjangoItem) -> DomainItem:
        return DomainItem(
            id=model.id,
            checklist_id=model.checklist_id,
            description=model.description,
            status=ChecklistItemStatus(model.status),
            due_date=model.due_date,
            assigned_to=model.assigned_to,
            order=model.order,
            created_at=model.created_at,
            updated_at=model.updated_at,
        )