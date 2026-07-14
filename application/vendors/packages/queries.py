from __future__ import annotations

from dataclasses import dataclass
import uuid

from domain.vendors.shared.pagination import PageRequest
from application.vendors.shared.commands import AuthenticatedActor
from application.vendors.shared.queries import _coerce_actor, _coerce_uuid

@dataclass(frozen=True)
class ListServicePackagesQuery:
    actor: AuthenticatedActor
    vendor_id: uuid.UUID
    page: PageRequest | None = None
    search_text: str | None = None

    def __post_init__(self) -> None:
        object.__setattr__(self, "actor", _coerce_actor(self.actor))
        object.__setattr__(self, "vendor_id", _coerce_uuid(self.vendor_id, "vendor_id"))
        if self.search_text is not None:
            search_text = str(self.search_text).strip()
            object.__setattr__(self, "search_text", search_text or None)
