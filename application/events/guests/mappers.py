from domain.events.guests.entity import GuestEntry

from application.events.guests.dtos import GuestEntryDTO


def to_guest_dto(g: GuestEntry) -> GuestEntryDTO:
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

