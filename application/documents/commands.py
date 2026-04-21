from dataclasses import dataclass
import uuid


@dataclass(frozen=True)
class RequestExportCommand:
    event_id: uuid.UUID
    requested_by: uuid.UUID
    export_type: str  # "event_brief", "timeline", "budget", "guest_list"