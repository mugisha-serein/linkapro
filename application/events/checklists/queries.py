from dataclasses import dataclass
import uuid


@dataclass(frozen=True)
class GetChecklistQuery:
    checklist_id: uuid.UUID


@dataclass(frozen=True)
class ListChecklistsByEventQuery:
    event_id: uuid.UUID

