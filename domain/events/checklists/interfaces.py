from abc import ABC, abstractmethod
from typing import List, Optional
import uuid

from domain.events.checklists.entity import Checklist
from domain.events.checklists.item import ChecklistItem


class IChecklistRepository(ABC):
    @abstractmethod
    def get_by_id(self, checklist_id: uuid.UUID) -> Optional[Checklist]: ...

    @abstractmethod
    def list_by_event(self, event_id: uuid.UUID) -> List[Checklist]: ...

    @abstractmethod
    def save(self, checklist: Checklist) -> Checklist: ...

    @abstractmethod
    def delete(self, checklist_id: uuid.UUID) -> None: ...


class IChecklistItemRepository(ABC):
    @abstractmethod
    def get_by_id(self, item_id: uuid.UUID) -> Optional[ChecklistItem]: ...

    @abstractmethod
    def list_by_checklist(self, checklist_id: uuid.UUID) -> List[ChecklistItem]: ...

    @abstractmethod
    def save(self, item: ChecklistItem) -> ChecklistItem: ...

    @abstractmethod
    def delete(self, item_id: uuid.UUID) -> None: ...

