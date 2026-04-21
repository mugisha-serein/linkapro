from dataclasses import dataclass
from datetime import datetime
from typing import Optional
import uuid


@dataclass(frozen=True)
class ExportJobDTO:
    id: uuid.UUID
    event_id: uuid.UUID
    export_type: str
    status: str
    file_url: Optional[str]
    error_message: Optional[str]
    created_at: datetime