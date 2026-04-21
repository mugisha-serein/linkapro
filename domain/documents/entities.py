"""Document generation domain entities."""
import uuid
from dataclasses import dataclass, field
from datetime import datetime
from enum import Enum
from typing import Optional

from domain.shared.utils import utc_now


class ExportType(str, Enum):
    EVENT_BRIEF = "event_brief"
    TIMELINE = "timeline"
    BUDGET = "budget"
    GUEST_LIST = "guest_list"


class ExportStatus(str, Enum):
    PENDING = "pending"
    PROCESSING = "processing"
    COMPLETED = "completed"
    FAILED = "failed"


@dataclass
class ExportJob:
    id: uuid.UUID
    event_id: uuid.UUID
    requested_by: uuid.UUID
    export_type: ExportType
    status: ExportStatus = ExportStatus.PENDING
    file_url: Optional[str] = None
    error_message: Optional[str] = None
    created_at: datetime = field(default_factory=utc_now)
    updated_at: datetime = field(default_factory=utc_now)

    def mark_processing(self) -> None:
        self.status = ExportStatus.PROCESSING
        self.updated_at = utc_now()

    def complete(self, file_url: str) -> None:
        self.status = ExportStatus.COMPLETED
        self.file_url = file_url
        self.updated_at = utc_now()

    def fail(self, error: str) -> None:
        self.status = ExportStatus.FAILED
        self.error_message = error
        self.updated_at = utc_now()