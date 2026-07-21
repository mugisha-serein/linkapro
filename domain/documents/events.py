from dataclasses import dataclass
import uuid
from datetime import datetime

from .entities import ExportType


@dataclass(frozen=True)
class ExportRequested:
    job_id: uuid.UUID
    event_id: uuid.UUID
    export_type: ExportType
    requested_by: uuid.UUID
    occurred_at: datetime


@dataclass(frozen=True)
class ExportCompleted:
    job_id: uuid.UUID
    event_id: uuid.UUID
    outbox_event_id: uuid.UUID
    export_type: ExportType
    requested_by: uuid.UUID
    file_url: str
    occurred_at: datetime
