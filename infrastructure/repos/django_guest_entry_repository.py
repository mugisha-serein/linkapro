import uuid
from typing import Optional, List
from django.core.exceptions import ObjectDoesNotExist

from domain.events.entities import GuestEntry as DomainGuest, RSVPStatus, DietaryRestriction
from domain.events.interfaces import IGuestEntryRepository
from django_app.events.models import GuestEntry as DjangoGuest, Event as DjangoEvent


class DjangoGuestEntryRepository(IGuestEntryRepository):
    def get_by_id(self, guest_id: uuid.UUID) -> Optional[DomainGuest]:
        try:
            obj = DjangoGuest.objects.select_related("event").get(id=guest_id)
            return self._to_domain(obj)
        except ObjectDoesNotExist:
            return None

    def list_by_event(self, event_id: uuid.UUID) -> List[DomainGuest]:
        objs = DjangoGuest.objects.filter(event_id=event_id)
        return [self._to_domain(o) for o in objs]

    def save(self, domain_guest: DomainGuest) -> DomainGuest:
        try:
            obj = DjangoGuest.objects.get(id=domain_guest.id)
        except DjangoGuest.DoesNotExist:
            obj = DjangoGuest(id=domain_guest.id)

        obj.event = DjangoEvent.objects.get(id=domain_guest.event_id)
        obj.full_name = domain_guest.full_name
        obj.email = domain_guest.email
        obj.phone = domain_guest.phone
        obj.rsvp_status = domain_guest.rsvp_status.value
        obj.dietary_restrictions = [r.value for r in domain_guest.dietary_restrictions]
        obj.plus_one = domain_guest.plus_one
        obj.table_assignment = domain_guest.table_assignment
        obj.notes = domain_guest.notes
        obj.save()
        return self._to_domain(obj)

    def delete(self, guest_id: uuid.UUID) -> None:
        DjangoGuest.objects.filter(id=guest_id).delete()

    def _to_domain(self, model: DjangoGuest) -> DomainGuest:
        restrictions = [DietaryRestriction(r) for r in model.dietary_restrictions]
        return DomainGuest(
            id=model.id,
            event_id=model.event_id,
            full_name=model.full_name,
            email=model.email,
            phone=model.phone,
            rsvp_status=RSVPStatus(model.rsvp_status),
            dietary_restrictions=restrictions,
            plus_one=model.plus_one,
            table_assignment=model.table_assignment,
            notes=model.notes,
            created_at=model.created_at,
            updated_at=model.updated_at,
        )