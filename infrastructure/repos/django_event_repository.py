import uuid
from typing import Optional, List
from django.core.exceptions import ObjectDoesNotExist

from domain.events.entities import Event as DomainEvent, EventType
from domain.events.interfaces import IEventRepository
from django_app.events.models import Event as DjangoEvent
from django_app.identity.models import User as DjangoUser


class DjangoEventRepository(IEventRepository):
    def get_by_id(self, event_id: uuid.UUID) -> Optional[DomainEvent]:
        try:
            event = DjangoEvent.objects.select_related("planner").get(id=event_id)
            return self._to_domain(event)
        except ObjectDoesNotExist:
            return None

    def list_by_planner(self, planner_id: uuid.UUID) -> List[DomainEvent]:
        events = DjangoEvent.objects.filter(planner_id=planner_id).select_related("planner")
        return [self._to_domain(e) for e in events]

    def save(self, domain_event: DomainEvent) -> DomainEvent:
        try:
            django_event = DjangoEvent.objects.get(id=domain_event.id)
        except DjangoEvent.DoesNotExist:
            django_event = DjangoEvent(id=domain_event.id)

        django_event.planner = DjangoUser.objects.get(id=domain_event.planner_id)
        django_event.name = domain_event.name
        django_event.event_type = domain_event.event_type.value
        django_event.event_date = domain_event.event_date
        django_event.venue = domain_event.venue
        django_event.expected_guests = domain_event.expected_guests
        django_event.total_budget = domain_event.total_budget
        django_event.save()
        return self._to_domain(django_event)

    def delete(self, event_id: uuid.UUID) -> None:
        DjangoEvent.objects.filter(id=event_id).delete()

    def _to_domain(self, model: DjangoEvent) -> DomainEvent:
        return DomainEvent(
            id=model.id,
            planner_id=model.planner_id,
            name=model.name,
            event_type=EventType(model.event_type),
            event_date=model.event_date,
            venue=model.venue,
            expected_guests=model.expected_guests,
            total_budget=float(model.total_budget),
            created_at=model.created_at,
            updated_at=model.updated_at,
        )