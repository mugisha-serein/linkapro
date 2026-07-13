from __future__ import annotations

import uuid

from application.vendors.errors import InvalidVendorCommand
from application.vendors.shared.commands import AuthenticatedActor

def _coerce_uuid(value, field_name: str) -> uuid.UUID:
    if isinstance(value, uuid.UUID):
        return value
    try:
        return uuid.UUID(str(value))
    except (TypeError, ValueError) as exc:
        raise InvalidVendorCommand(field_errors={field_name: ["Must be a valid UUID."]}) from exc

def _coerce_actor(value: AuthenticatedActor) -> AuthenticatedActor:
    if not isinstance(value, AuthenticatedActor):
        raise InvalidVendorCommand(field_errors={"actor": ["Authenticated actor is required."]})
    return value
