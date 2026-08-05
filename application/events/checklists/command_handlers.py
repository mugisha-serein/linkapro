"""Checklist command handlers for the event planning application layer."""

import uuid

from domain.events.checklists.errors import ChecklistNotFound
from domain.events.checklists.entity import Checklist
from domain.events.checklists.interfaces import IChecklistItemRepository, IChecklistRepository
from domain.events.checklists.item import ChecklistItem
from domain.events.checklists.value_objects import ChecklistItemStatus
from domain.events.domain_events import ChecklistCreated
from domain.shared.utils import utc_now

from application.events.commands import (
    AddChecklistItemCommand,
    CreateChecklistCommand,
    UpdateChecklistItemCommand,
)
from application.events.dtos import ChecklistDTO, ChecklistItemDTO


class ChecklistCommandHandlers:
    def __init__(
        self,
        checklist_repo: IChecklistRepository,
        checklist_item_repo: IChecklistItemRepository,
        event_dispatcher,
    ):
        self.checklist_repo = checklist_repo
        self.checklist_item_repo = checklist_item_repo
        self.event_dispatcher = event_dispatcher

    def create_checklist(self, cmd: CreateChecklistCommand) -> ChecklistDTO:
        checklist = Checklist(
            id=uuid.uuid4(),
            event_id=cmd.event_id,
            name=cmd.name,
        )
        saved = self.checklist_repo.save(checklist)
        self.event_dispatcher.dispatch(
            ChecklistCreated(checklist_id=saved.id, event_id=saved.event_id, occurred_at=utc_now())
        )
        return self._to_checklist_dto(saved)

    def add_checklist_item(self, cmd: AddChecklistItemCommand) -> ChecklistItemDTO:
        existing = self.checklist_item_repo.list_by_checklist(cmd.checklist_id)
        max_order = max([i.order for i in existing], default=-1)
        item = ChecklistItem(
            id=uuid.uuid4(),
            checklist_id=cmd.checklist_id,
            description=cmd.description,
            due_date=cmd.due_date,
            assigned_to=cmd.assigned_to,
            order=max_order + 1,
        )
        saved = self.checklist_item_repo.save(item)
        return self._to_item_dto(saved)

    def update_checklist_item(self, cmd: UpdateChecklistItemCommand) -> ChecklistItemDTO:
        item = self.checklist_item_repo.get_by_id(cmd.item_id)
        if not item:
            raise ChecklistNotFound("Checklist item not found")
        item.update(description=cmd.description, due_date=cmd.due_date)
        if cmd.status is not None:
            item.status = ChecklistItemStatus(cmd.status)
        if cmd.assigned_to is not None:
            item.assigned_to = cmd.assigned_to
        saved = self.checklist_item_repo.save(item)
        return self._to_item_dto(saved)

    @staticmethod
    def _to_checklist_dto(c: Checklist) -> ChecklistDTO:
        return ChecklistDTO(id=c.id, event_id=c.event_id, name=c.name)

    @staticmethod
    def _to_item_dto(i: ChecklistItem) -> ChecklistItemDTO:
        return ChecklistItemDTO(
            id=i.id,
            checklist_id=i.checklist_id,
            description=i.description,
            status=i.status.value,
            due_date=i.due_date,
            assigned_to=i.assigned_to,
            order=i.order,
        )
