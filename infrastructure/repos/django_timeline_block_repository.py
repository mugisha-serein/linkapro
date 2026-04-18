import uuid
from typing import Optional, List
from django.core.exceptions import ObjectDoesNotExist

from domain.events.entities import TimelineBlock as DomainBlock
from domain.events.interfaces import ITimelineBlockRepository
from django_app.events.models import TimelineBlock as DjangoBlock, Event as DjangoEvent


class DjangoTimelineBlockRepository(ITimelineBlockRepository):
    def get_by_id(self, block_id: uuid.UUID) -> Optional[DomainBlock]:
        try:
            obj = DjangoBlock.objects.select_related("event").get(id=block_id)
            return self._to_domain(obj)
        except ObjectDoesNotExist:
            return None

    def list_by_event(self, event_id: uuid.UUID) -> List[DomainBlock]:
        objs = DjangoBlock.objects.filter(event_id=event_id).order_by("order")
        return [self._to_domain(o) for o in objs]

    def save(self, domain_block: DomainBlock) -> DomainBlock:
        try:
            obj = DjangoBlock.objects.get(id=domain_block.id)
        except DjangoBlock.DoesNotExist:
            obj = DjangoBlock(id=domain_block.id)

        obj.event = DjangoEvent.objects.get(id=domain_block.event_id)
        obj.title = domain_block.title
        obj.start_time = domain_block.start_time
        obj.end_time = domain_block.end_time
        obj.description = domain_block.description
        obj.location = domain_block.location
        obj.order = domain_block.order
        obj.save()
        return self._to_domain(obj)

    def delete(self, block_id: uuid.UUID) -> None:
        DjangoBlock.objects.filter(id=block_id).delete()

    def _to_domain(self, model: DjangoBlock) -> DomainBlock:
        return DomainBlock(
            id=model.id,
            event_id=model.event_id,
            title=model.title,
            start_time=model.start_time,
            end_time=model.end_time,
            description=model.description,
            location=model.location,
            order=model.order,
            created_at=model.created_at,
            updated_at=model.updated_at,
        )