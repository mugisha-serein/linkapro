from dataclasses import dataclass
from datetime import date
from typing import Optional
import uuid


@dataclass(frozen=True)
class ChecklistDTO:
    id: uuid.UUID
    event_id: uuid.UUID
    name: str


@dataclass(frozen=True)
class ChecklistItemDTO:
    id: uuid.UUID
    checklist_id: uuid.UUID
    description: str
    status: str
    due_date: Optional[date]
    assigned_to: Optional[str]
    order: int

