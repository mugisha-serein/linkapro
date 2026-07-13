from __future__ import annotations

from dataclasses import dataclass
from typing import Iterable, Mapping, TypeAlias, TypeVar
import uuid

from application.vendors.errors import InvalidVendorCommand

T = TypeVar("T")
MAX_IDEMPOTENCY_KEY_LENGTH = 200

class _Omitted:
    def __repr__(self) -> str:
        return "OMITTED"

def _coerce_uuid(value, field_name: str) -> uuid.UUID:
    if isinstance(value, uuid.UUID):
        return value
    try:
        return uuid.UUID(str(value))
    except (TypeError, ValueError) as exc:
        raise InvalidVendorCommand(field_errors={field_name: ["Must be a valid UUID."]}) from exc

def _coerce_expected_version(value, field_name: str = "expected_version") -> int:
    if not isinstance(value, int) or isinstance(value, bool) or value < 0:
        raise InvalidVendorCommand(field_errors={field_name: ["Must be a nonnegative integer."]})
    return value

def _coerce_optional_idempotency_key(value: str | None) -> str | None:
    if value is None:
        return None
    return _coerce_required_idempotency_key(value)

def _coerce_required_idempotency_key(value: str) -> str:
    if not isinstance(value, str) or not value.strip():
        raise InvalidVendorCommand(field_errors={"idempotency_key": ["Must be a nonblank string."]})
    key = value.strip()
    if len(key) > MAX_IDEMPOTENCY_KEY_LENGTH:
        raise InvalidVendorCommand(field_errors={"idempotency_key": ["Must be 200 characters or fewer."]})
    return key

def _coerce_actor(value: AuthenticatedActor) -> AuthenticatedActor:
    if not isinstance(value, AuthenticatedActor):
        raise InvalidVendorCommand(field_errors={"actor": ["Authenticated actor is required."]})
    return value

def _coerce_moderator(value: ModeratorActor) -> ModeratorActor:
    if not isinstance(value, ModeratorActor):
        raise InvalidVendorCommand(field_errors={"moderator": ["Moderator actor is required."]})
    return value

@dataclass(frozen=True)
class AuthenticatedActor:
    user_id: uuid.UUID

    def __post_init__(self) -> None:
        object.__setattr__(self, "user_id", _coerce_uuid(self.user_id, "actor.user_id"))

@dataclass(frozen=True)
class ModeratorActor:
    user_id: uuid.UUID

    def __post_init__(self) -> None:
        object.__setattr__(self, "user_id", _coerce_uuid(self.user_id, "moderator.user_id"))

@dataclass(frozen=True)
class ResourceVersion:
    resource_id: uuid.UUID
    expected_version: int

    def __post_init__(self) -> None:
        object.__setattr__(self, "resource_id", _coerce_uuid(self.resource_id, "resource_id"))
        object.__setattr__(self, "expected_version", _coerce_expected_version(self.expected_version))

def _coerce_resource_versions(value: Iterable[ResourceVersion] | Mapping[uuid.UUID, int]) -> tuple[ResourceVersion, ...]:
    if isinstance(value, Mapping):
        versions = tuple(ResourceVersion(resource_id=key, expected_version=version) for key, version in value.items())
    else:
        versions = tuple(value)
    if not versions:
        raise InvalidVendorCommand(field_errors={"expected_versions": ["At least one version is required."]})
    if any(not isinstance(version, ResourceVersion) for version in versions):
        raise InvalidVendorCommand(
            field_errors={"expected_versions": ["Every item must be a ResourceVersion."]}
        )
    resource_ids = tuple(version.resource_id for version in versions)
    if len(resource_ids) != len(set(resource_ids)):
        raise InvalidVendorCommand(
            field_errors={"expected_versions": ["Duplicate resource IDs are not allowed."]}
        )
    return versions

OmittedValue: TypeAlias = T | _Omitted
OMITTED = _Omitted()
