import uuid
from dataclasses import dataclass, field
from datetime import date, datetime
from typing import Optional

from domain.events.checklists.errors import InvalidChecklistItem
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

    def __post_init__(self) -> None:
        self._validate_description(self.description)

    def mark_completed(self) -> None:
        self.status = ChecklistItemStatus.COMPLETED
        self.updated_at = utc_now()

    def mark_in_progress(self) -> None:
        self.status = ChecklistItemStatus.IN_PROGRESS
        self.updated_at = utc_now()

    def update(self, description: str | None = None, due_date: date | None = None) -> None:
        changed = False
        if description is not None:
            self._validate_description(description)
            self.description = description
            changed = True
        if due_date is not None:
            if not isinstance(due_date, date) or isinstance(due_date, datetime):
                raise ValueError("Due date must be a date")
            self.due_date = due_date
            changed = True
        if changed:
            self.updated_at = utc_now()

    def update_description(self, new_desc: str) -> None:
        self._validate_description(new_desc)
        self.description = new_desc
        self.updated_at = utc_now()

    @staticmethod
    def _validate_description(description: str) -> None:
        if not isinstance(description, str) or not description.strip():
            raise InvalidChecklistItem("Checklist item description must not be blank")
