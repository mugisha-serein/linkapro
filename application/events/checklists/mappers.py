from domain.events.checklists.entity import Checklist
from domain.events.checklists.item import ChecklistItem

from application.events.checklists.dtos import ChecklistDTO, ChecklistItemDTO


def to_checklist_dto(c: Checklist) -> ChecklistDTO:
    return ChecklistDTO(id=c.id, event_id=c.event_id, name=c.name)


def to_checklist_item_dto(i: ChecklistItem) -> ChecklistItemDTO:
    return ChecklistItemDTO(
        id=i.id,
        checklist_id=i.checklist_id,
        description=i.description,
        status=i.status.value,
        due_date=i.due_date,
        assigned_to=i.assigned_to,
        order=i.order,
    )

