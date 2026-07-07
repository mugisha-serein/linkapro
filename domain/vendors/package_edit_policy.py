from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime, timedelta
from decimal import Decimal
from typing import Optional

from domain.vendors.errors import PackageValidationError, VendorDomainError
from domain.vendors.package_rules import coerce_package_price
from domain.vendors.validation import aware_utc_datetime, bounded_text, normalize_currency

VENDOR_PACKAGE_EDIT_COOLDOWN_DAYS = 15
VENDOR_PACKAGE_EDIT_COOLDOWN = timedelta(days=VENDOR_PACKAGE_EDIT_COOLDOWN_DAYS)


@dataclass
class PackageEditCooldownError(VendorDomainError):
    next_allowed_at: datetime
    message: str = "Package changes are allowed only once every 15 days after approval."

    code: str = "vendor_package_edit_cooldown_active"

    def __post_init__(self) -> None:
        super().__init__(self.message, code=self.code)


def package_public_fields_changed(
    package,
    *,
    name: Optional[str] = None,
    description: Optional[str] = None,
    price: Optional[Decimal] = None,
    currency: Optional[str] = None,
    package_tier: Optional[str] = None,
) -> bool:
    if name is not None and _normalize_public_text(name) != _normalize_public_text(package.name):
        return True
    if description is not None and _normalize_public_text(description) != _normalize_public_text(package.description):
        return True
    if price is not None and coerce_package_price(price) != package.price:
        return True
    if currency is not None and normalize_currency(currency) != normalize_currency(package.currency):
        return True
    if package_tier is not None and (
        (package_tier or "").strip().lower() != (package.package_tier or "").strip().lower()
    ):
        return True
    return False


def approval_based_next_edit_allowed_at(package) -> Optional[datetime]:
    if package.approval_status != "approved":
        return None
    approved_at = _normalize_timestamp(package.last_approved_at or package.updated_at, "last_approved_at")
    if not approved_at:
        return None
    return approved_at + VENDOR_PACKAGE_EDIT_COOLDOWN


def effective_next_edit_allowed_at(package) -> Optional[datetime]:
    stored_next_allowed = _normalize_timestamp(package.next_vendor_edit_allowed_at, "next_vendor_edit_allowed_at")
    approval_next_allowed = approval_based_next_edit_allowed_at(package)
    last_edit = _normalize_timestamp(package.last_vendor_public_edit_at, "last_vendor_public_edit_at")
    if stored_next_allowed and last_edit and stored_next_allowed < last_edit:
        raise PackageValidationError(
            field_errors={"next_vendor_edit_allowed_at": ["Next edit time cannot be before the last edit."]}
        )
    if stored_next_allowed and approval_next_allowed:
        return max(stored_next_allowed, approval_next_allowed)
    return stored_next_allowed or approval_next_allowed


def ensure_vendor_package_edit_allowed(package, *, public_fields_changed: bool, now: datetime) -> None:
    now = _normalize_timestamp(now, "now", required=True)
    if not public_fields_changed:
        return
    next_allowed = effective_next_edit_allowed_at(package)
    if next_allowed and now < next_allowed:
        raise PackageEditCooldownError(next_allowed_at=next_allowed)


def package_public_edit_markers(package, *, now: datetime, public_fields_changed: bool) -> dict:
    now = _normalize_timestamp(now, "now", required=True)
    if not public_fields_changed:
        return {}
    effective_next_edit_allowed_at(package)
    return {
        "approval_status": "waiting_approval",
        "rejection_reason": None,
        "is_active": False,
        "last_vendor_public_edit_at": now,
        "next_vendor_edit_allowed_at": now + VENDOR_PACKAGE_EDIT_COOLDOWN,
    }


def mark_vendor_package_public_edit(package, *, now: datetime, public_fields_changed: bool) -> dict:
    return package_public_edit_markers(package, now=now, public_fields_changed=public_fields_changed)


def _normalize_public_text(value: str) -> str:
    return bounded_text(value, field_name="public_field", max_length=5000).strip()


def _normalize_timestamp(value, field_name: str, *, required: bool = False):
    try:
        return aware_utc_datetime(value, field_name=field_name, required=required)
    except ValueError as exc:
        raise PackageValidationError(field_errors={field_name: [str(exc)]}) from exc
