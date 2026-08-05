from typing import List, Optional
import uuid

from domain.events.checklists.interfaces import IChecklistItemRepository, IChecklistRepository

from application.events.checklists.dtos import ChecklistDTO, ChecklistItemDTO
from application.events.checklists.mappers import to_checklist_dto, to_checklist_item_dto


class ChecklistQueryHandlers:
    def __init__(
        self,
        checklist_repo: IChecklistRepository,
        checklist_item_repo: IChecklistItemRepository,
    ):
        self.checklist_repo = checklist_repo
        self.checklist_item_repo = checklist_item_repo

    def get_checklist(self, checklist_id: uuid.UUID) -> Optional[ChecklistDTO]:
        checklist = self.checklist_repo.get_by_id(checklist_id)
        if not checklist:
            return None
        return to_checklist_dto(checklist)

    def list_checklists_by_event(self, event_id: uuid.UUID) -> List[ChecklistDTO]:
        checklists = self.checklist_repo.list_by_event(event_id)
        return [to_checklist_dto(c) for c in checklists]

    def list_checklist_items(self, checklist_id: uuid.UUID) -> List[ChecklistItemDTO]:
        items = self.checklist_item_repo.list_by_checklist(checklist_id)
        return [to_checklist_item_dto(i) for i in items]

