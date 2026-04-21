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