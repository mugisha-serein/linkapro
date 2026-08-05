"""Guest command handlers for the event planning application layer."""

import uuid

from domain.events.domain_events import GuestAdded
from domain.events.guests.entity import GuestEntry
from domain.events.guests.errors import GuestNotFound
from domain.events.guests.interfaces import IGuestEntryRepository
from domain.events.guests.value_objects import DietaryRestriction, RSVPStatus
from domain.shared.utils import utc_now

from application.events.commands import AddGuestCommand, UpdateGuestCommand
from application.events.dtos import GuestEntryDTO


class GuestCommandHandlers:
    def __init__(self, guest_repo: IGuestEntryRepository, event_dispatcher):
        self.guest_repo = guest_repo
        self.event_dispatcher = event_dispatcher

    def add_guest(self, cmd: AddGuestCommand) -> GuestEntryDTO:
        restrictions = [DietaryRestriction(r) for r in cmd.dietary_restrictions]
        guest = GuestEntry(
            id=uuid.uuid4(),
            event_id=cmd.event_id,
            full_name=cmd.full_name,
            email=cmd.email,
            phone=cmd.phone,
            dietary_restrictions=restrictions,
            plus_one=cmd.plus_one,
            notes=cmd.notes,
        )
        saved = self.guest_repo.save(guest)
        self.event_dispatcher.dispatch(
            GuestAdded(guest_id=saved.id, event_id=saved.event_id, occurred_at=utc_now())
        )
        return self._to_guest_dto(saved)

    def update_guest(self, cmd: UpdateGuestCommand) -> GuestEntryDTO:
        guest = self.guest_repo.get_by_id(cmd.guest_id)
        if not guest:
            raise GuestNotFound("Guest not found")
        guest.update_contact(full_name=cmd.full_name, email=cmd.email, phone=cmd.phone)
        if cmd.rsvp_status is not None:
            guest.rsvp_status = RSVPStatus(cmd.rsvp_status)
        if cmd.dietary_restrictions is not None:
            guest.dietary_restrictions = [DietaryRestriction(r) for r in cmd.dietary_restrictions]
        if cmd.plus_one is not None:
            guest.plus_one = cmd.plus_one
        if cmd.table_assignment is not None:
            guest.table_assignment = cmd.table_assignment
        if cmd.notes is not None:
            guest.notes = cmd.notes
        saved = self.guest_repo.save(guest)
        return self._to_guest_dto(saved)

    @staticmethod
    def _to_guest_dto(g: GuestEntry) -> GuestEntryDTO:
        return GuestEntryDTO(
            id=g.id,
            event_id=g.event_id,
            full_name=g.full_name,
            email=g.email,
            phone=g.phone,
            rsvp_status=g.rsvp_status.value,
            dietary_restrictions=[r.value for r in g.dietary_restrictions],
            plus_one=g.plus_one,
            table_assignment=g.table_assignment,
            notes=g.notes,
        )
