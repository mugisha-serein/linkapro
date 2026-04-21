from dataclasses import dataclass
import uuid
from datetime import datetime

from .entities import AdminActionType


@dataclass(frozen=True)
class AdminActionPerformed:
    admin_id: uuid.UUID
    action_type: AdminActionType
    target_type: str
    target_id: uuid.UUID
    occurred_at: datetime