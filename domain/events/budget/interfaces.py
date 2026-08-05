from abc import ABC, abstractmethod
from typing import List, Optional
import uuid

from domain.events.budget.entity import BudgetLine


class IBudgetLineRepository(ABC):
    @abstractmethod
    def get_by_id(self, line_id: uuid.UUID) -> Optional[BudgetLine]: ...

    @abstractmethod
    def list_by_event(self, event_id: uuid.UUID) -> List[BudgetLine]: ...

    @abstractmethod
    def save(self, line: BudgetLine) -> BudgetLine: ...

    @abstractmethod
    def delete(self, line_id: uuid.UUID) -> None: ...

