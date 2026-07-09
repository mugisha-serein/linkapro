from __future__ import annotations

from dataclasses import dataclass
import uuid

from .commands import AuthenticatedActor, _coerce_actor, _coerce_expected_version, _coerce_uuid


@dataclass(frozen=True)
class QueuePortfolioMediaCommand:
    actor: AuthenticatedActor
    vendor_id: uuid.UUID
    media_id: uuid.UUID
    expected_version: int

    def __post_init__(self) -> None:
        object.__setattr__(self, "actor", _coerce_actor(self.actor))
        object.__setattr__(self, "vendor_id", _coerce_uuid(self.vendor_id, "vendor_id"))
        object.__setattr__(self, "media_id", _coerce_uuid(self.media_id, "media_id"))
        object.__setattr__(self, "expected_version", _coerce_expected_version(self.expected_version))


@dataclass(frozen=True)
class MarkPortfolioMediaProcessingCommand:
    actor: AuthenticatedActor
    vendor_id: uuid.UUID
    media_id: uuid.UUID
    expected_version: int

    def __post_init__(self) -> None:
        object.__setattr__(self, "actor", _coerce_actor(self.actor))
        object.__setattr__(self, "vendor_id", _coerce_uuid(self.vendor_id, "vendor_id"))
        object.__setattr__(self, "media_id", _coerce_uuid(self.media_id, "media_id"))
        object.__setattr__(self, "expected_version", _coerce_expected_version(self.expected_version))
