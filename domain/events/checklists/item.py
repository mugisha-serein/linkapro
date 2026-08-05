import uuid
from dataclasses import dataclass, field
from datetime import date, datetime
from typing import Optional

from domain.events.checklists.value_objects import ChecklistItemStatus
from domain.shared.utils import utc_now


@dataclass
class ChecklistItem:
    """Individual task within a checklist."""

    id: uuid.UUID
    checklist_id: uuid.UUID
    description: str
    status: ChecklistItemStatus = ChecklistItemStatus.PENDING
    due_date: Optional[date] = None
    assigned_to: Optional[str] = None
    order: int = 0
    created_at: datetime = field(default_factory=utc_now)
    updated_at: datetime = field(default_factory=utc_now)

    def mark_completed(self) -> None:
        self.status = ChecklistItemStatus.COMPLETED
        self.updated_at = utc_now()

    def mark_in_progress(self) -> None:
        self.status = ChecklistItemStatus.IN_PROGRESS
        self.updated_at = utc_now()

    def update_description(self, new_desc: str) -> None:
        self.description = new_desc
        self.updated_at = utc_now()

