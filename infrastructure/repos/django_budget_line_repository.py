import uuid
from typing import Optional, List
from django.core.exceptions import ObjectDoesNotExist

from domain.events.entities import BudgetLine as DomainLine, BudgetCategory
from domain.events.interfaces import IBudgetLineRepository
from django_app.events.models import BudgetLine as DjangoLine, Event as DjangoEvent


class DjangoBudgetLineRepository(IBudgetLineRepository):
    def get_by_id(self, line_id: uuid.UUID) -> Optional[DomainLine]:
        try:
            obj = DjangoLine.objects.select_related("event").get(id=line_id)
            return self._to_domain(obj)
        except ObjectDoesNotExist:
            return None

    def list_by_event(self, event_id: uuid.UUID) -> List[DomainLine]:
        objs = DjangoLine.objects.filter(event_id=event_id)
        return [self._to_domain(o) for o in objs]

    def save(self, domain_line: DomainLine) -> DomainLine:
        try:
            obj = DjangoLine.objects.get(id=domain_line.id)
        except DjangoLine.DoesNotExist:
            obj = DjangoLine(id=domain_line.id)

        obj.event = DjangoEvent.objects.get(id=domain_line.event_id)
        obj.category = domain_line.category.value
        obj.description = domain_line.description
        obj.estimated_cost = domain_line.estimated_cost
        obj.actual_cost = domain_line.actual_cost
        obj.notes = domain_line.notes
        obj.save()
        return self._to_domain(obj)

    def delete(self, line_id: uuid.UUID) -> None:
        DjangoLine.objects.filter(id=line_id).delete()

    def _to_domain(self, model: DjangoLine) -> DomainLine:
        return DomainLine(
            id=model.id,
            event_id=model.event_id,
            category=BudgetCategory(model.category),
            description=model.description,
            estimated_cost=float(model.estimated_cost),
            actual_cost=float(model.actual_cost) if model.actual_cost else None,
            notes=model.notes,
            created_at=model.created_at,
            updated_at=model.updated_at,
        )