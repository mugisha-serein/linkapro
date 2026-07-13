from __future__ import annotations

import uuid
from dataclasses import dataclass, field
from datetime import date, datetime
from decimal import Decimal
from typing import Callable, ClassVar

from domain.vendors.shared.validation import (
    TEXT_LIMITS,
    add_error,
    aware_utc_datetime,
    bounded_text,
    normalize_currency,
    normalize_event_date,
    normalize_phone,
    positive_decimal,
    validate_bool,
    validate_email,
    validate_int,
    validate_optional_int,
    validate_public_media_url,
    validate_safe_url,
    validate_uuid,
)

class VendorDomainError(ValueError):
    default_code = "vendor_domain_error"

    def __init__(
        self,
        message: str | None = None,
        *,
        code: str | None = None,
        field_errors: dict[str, list[str]] | None = None,
    ) -> None:
        self.code = code or self.default_code
        self.field_errors = field_errors or {}
        self.errors = self.field_errors
        super().__init__(message or self.code)

class ConcurrentVendorUpdate(VendorDomainError):
    default_code = "vendor_concurrent_update"

class ProtectedStateMutationError(VendorDomainError):
    default_code = "vendor_protected_state_assignment"

@dataclass(frozen=True, kw_only=True)
class VendorDomainEvent:
    occurred_at: datetime
    aggregate_id: uuid.UUID
    aggregate_version: int
    event_id: uuid.UUID = field(default_factory=uuid.uuid4)

    def __post_init__(self) -> None:
        if not isinstance(self.event_id, uuid.UUID):
            raise TypeError("event_id must be a UUID.")
        if not isinstance(self.aggregate_id, uuid.UUID):
            raise TypeError("aggregate_id must be a UUID.")
        if (
            not isinstance(self.aggregate_version, int)
            or isinstance(self.aggregate_version, bool)
            or self.aggregate_version < 0
        ):
            raise ValueError("aggregate_version must be a nonnegative integer.")
        if not isinstance(self.occurred_at, datetime):
            raise TypeError("occurred_at must be a datetime.")
        if self.occurred_at.tzinfo is None or self.occurred_at.utcoffset() is None:
            raise ValueError("occurred_at must be timezone-aware.")

_UNSET = object()

class DomainAggregate:
    version: int
    _events: list
    _protected_fields: ClassVar[frozenset[str]] = frozenset()

    def __setattr__(self, name: str, value) -> None:
        if (
            name in self._protected_fields
            and getattr(self, "_state_locked", False)
            and not getattr(self, "_allow_protected_assignment", False)
        ):
            raise ProtectedStateMutationError(
                f"Direct assignment to {name} is not allowed.",
                field_errors={name: ["Use a validated domain transition."]},
            )
        object.__setattr__(self, name, value)

    def _init_domain_state(self) -> None:
        if not hasattr(self, "_events") or self._events is None:
            object.__setattr__(self, "_events", [])
        object.__setattr__(self, "_state_locked", False)
        object.__setattr__(self, "_allow_protected_assignment", False)

    def _lock_state(self) -> None:
        object.__setattr__(self, "_state_locked", True)

    def _record(self, event) -> None:
        self._events.append(event)

    def pull_events(self) -> list:
        events = list(self._events)
        self._events.clear()
        return events

    def _bump_version(self) -> None:
        object.__setattr__(self, "version", self.version + 1)

    def _commit_candidate(self, candidate, event_factory: Callable[[int], object] | None = None) -> None:
        object.__setattr__(candidate, "_allow_protected_assignment", True)
        try:
            candidate.validate_invariants()
        finally:
            object.__setattr__(candidate, "_allow_protected_assignment", False)
        pending_events = list(self._events)
        for key, value in candidate.__dict__.items():
            if key != "_events":
                object.__setattr__(self, key, value)
        object.__setattr__(self, "_events", pending_events)
        self._lock_state()
        self._bump_version()
        if event_factory is not None:
            self._record(event_factory(self.version))

def _normalize_uuid(value, field_name: str, errors: dict[str, list[str]]) -> uuid.UUID:
    try:
        return validate_uuid(value, field_name=field_name)
    except ValueError as exc:
        add_error(errors, field_name, str(exc))
        return value

def _normalize_text(
    value,
    field_name: str,
    max_length: int,
    errors: dict[str, list[str]],
    *,
    min_length: int = 1,
) -> str:
    try:
        return bounded_text(value, field_name=field_name, max_length=max_length, min_length=min_length)
    except ValueError as exc:
        if field_name == "name" and str(exc) == "This field is required.":
            add_error(errors, field_name, "Package name is required.")
        else:
            add_error(errors, field_name, str(exc))
        return "" if value is None else str(value)

def _normalize_optional_text(
    value,
    field_name: str,
    max_length: int,
    errors: dict[str, list[str]],
) -> str | None:
    try:
        return bounded_text(value, field_name=field_name, max_length=max_length, required=False)
    except ValueError as exc:
        add_error(errors, field_name, str(exc))
        return value

def _normalize_email(value, field_name: str, errors: dict[str, list[str]]) -> str:
    try:
        return validate_email(value, field_name=field_name)
    except ValueError as exc:
        add_error(errors, field_name, str(exc))
        return "" if value is None else str(value)

def _normalize_phone(value, field_name: str, errors: dict[str, list[str]]) -> str:
    try:
        return normalize_phone(value)
    except ValueError as exc:
        add_error(errors, field_name, str(exc))
        return "" if value is None else str(value)

def _normalize_optional_phone(value, field_name: str, errors: dict[str, list[str]]) -> str | None:
    try:
        return normalize_phone(value, required=False)
    except ValueError as exc:
        add_error(errors, field_name, str(exc))
        return value

def _normalize_safe_url(value, field_name: str, errors: dict[str, list[str]]) -> str | None:
    try:
        return validate_safe_url(value, field_name=field_name)
    except ValueError as exc:
        add_error(errors, field_name, str(exc))
        return value

def _normalize_public_media_url(
    value,
    field_name: str,
    errors: dict[str, list[str]],
    *,
    required: bool = False,
) -> str | None:
    try:
        return validate_public_media_url(value, field_name=field_name, required=required)
    except ValueError as exc:
        add_error(errors, field_name, str(exc))
        return value

def _normalize_datetime(
    value,
    field_name: str,
    errors: dict[str, list[str]],
    *,
    required: bool = False,
) -> datetime | None:
    try:
        return aware_utc_datetime(value, field_name=field_name, required=required)
    except ValueError as exc:
        add_error(errors, field_name, str(exc))
        return value

def _normalize_event_date(value, field_name: str, errors: dict[str, list[str]]) -> date | None:
    try:
        return normalize_event_date(value, field_name=field_name)
    except ValueError as exc:
        add_error(errors, field_name, str(exc))
        return value

def _normalize_bool(value, field_name: str, errors: dict[str, list[str]]) -> bool:
    try:
        return validate_bool(value, field_name=field_name)
    except ValueError as exc:
        add_error(errors, field_name, str(exc))
        return value

def _normalize_int(
    value,
    field_name: str,
    errors: dict[str, list[str]],
    *,
    minimum: int | None = None,
    maximum: int | None = None,
) -> int:
    try:
        return validate_int(value, field_name=field_name, minimum=minimum, maximum=maximum)
    except ValueError as exc:
        add_error(errors, field_name, str(exc))
        return value

def _normalize_optional_int(
    value,
    field_name: str,
    errors: dict[str, list[str]],
    *,
    minimum: int | None = None,
    maximum: int | None = None,
) -> int | None:
    try:
        return validate_optional_int(value, field_name=field_name, minimum=minimum, maximum=maximum)
    except ValueError as exc:
        add_error(errors, field_name, str(exc))
        return value

def _normalize_version(value, errors: dict[str, list[str]]) -> int:
    try:
        return validate_int(value, field_name="version", minimum=0)
    except ValueError as exc:
        add_error(errors, "version", str(exc))
        return value

def _normalize_price(value, errors: dict[str, list[str]]) -> Decimal:
    try:
        return positive_decimal(value)
    except ValueError as exc:
        add_error(errors, "price", str(exc))
        try:
            from domain.vendors.packages.rules import coerce_package_price

            return coerce_package_price(value)
        except ValueError:
            return Decimal("0")

def _normalize_currency_value(value, errors: dict[str, list[str]]) -> str:
    try:
        return normalize_currency(value)
    except ValueError as exc:
        add_error(errors, "currency", str(exc))
        return "" if value is None else str(value)

def _normalize_enum(enum_cls, value, field_name: str, errors: dict[str, list[str]]):
    try:
        return value if isinstance(value, enum_cls) else enum_cls(value)
    except ValueError:
        add_error(errors, field_name, f"Choose a valid {field_name}.")
        return value

def _normalize_enum_value(enum_cls, value, field_name: str, errors: dict[str, list[str]]) -> str:
    enum_value = _normalize_enum(enum_cls, value, field_name, errors)
    return enum_value.value if isinstance(enum_value, enum_cls) else value

def _validate_public_id_url_pair(
    errors: dict[str, list[str]],
    *,
    url: str | None,
    public_id: str | None,
    url_field: str,
    public_id_field: str,
) -> None:
    if bool(url) != bool(public_id):
        add_error(errors, public_id_field if url else url_field, "Public ID and URL must be stored together.")

def _validated_transition_reason(reason: str, field_name: str, error_cls):
    errors: dict[str, list[str]] = {}
    clean_reason = _normalize_text(reason, field_name, TEXT_LIMITS["rejection_reason"], errors)
    if errors:
        raise error_cls(field_errors=errors)
    return clean_reason
