from decimal import Decimal, InvalidOperation

from domain.vendors.packages.errors import PackageValidationError
from domain.vendors.shared.validation import (
    MAX_PACKAGE_PRICE,
    TEXT_LIMITS,
    bounded_text,
    has_control_characters,
    positive_decimal,
)


PACKAGE_TIER_LABELS = {
    "standard": "Standard",
    "premier": "Premier",
    "gold": "Gold",
}

PACKAGE_TIER_RULES = {
    "standard": {"min_price": Decimal("1"), "min_description_length": 30},
    "premier": {"min_price": Decimal("50000"), "min_description_length": 50},
    "gold": {"min_price": Decimal("100000"), "min_description_length": 80},
}

RESTRICTED_STANDARD_TERMS = ("premium", "premier", "exclusive", "vip", "gold")
MISLEADING_GUARANTEE_TERMS = ("guaranteed approval", "guaranteed success", "risk-free guarantee")


def validate_service_package_rules(*, name: str, description: str, price, package_tier: str) -> None:
    errors: dict[str, list[str]] = {}
    tier = (package_tier or "").strip().lower()
    rules = PACKAGE_TIER_RULES.get(tier)

    if not rules:
        errors["package_tier"] = ["Choose Standard, Premier, or Gold."]
        raise PackageValidationError(field_errors=errors)

    clean_name = (name or "").strip()
    clean_description = (description or "").strip()
    price_value = _to_decimal(price)
    tier_label = PACKAGE_TIER_LABELS[tier]

    try:
        clean_name = bounded_text(name, field_name="name", max_length=TEXT_LIMITS["package_name"])
    except ValueError as exc:
        errors.setdefault("name", []).append("Package name is required." if not clean_name else str(exc))
    try:
        clean_description = bounded_text(
            description,
            field_name="description",
            max_length=TEXT_LIMITS["package_description"],
        )
    except ValueError as exc:
        errors.setdefault("description", []).append(str(exc))
    try:
        price_value = positive_decimal(price)
    except ValueError as exc:
        if "finite" in str(exc):
            errors.setdefault("price", []).append("Package price must be a finite amount.")
        elif "decimal places" in str(exc):
            errors.setdefault("price", []).append("Package price must use no more than 2 decimal places.")
        elif "no more" in str(exc):
            errors.setdefault("price", []).append(f"Package price must not exceed RWF {MAX_PACKAGE_PRICE:,.2f}.")
        else:
            errors.setdefault("price", []).append("Package price must be greater than 0.")
        price_value = None
    if price_value is not None and price_value < rules["min_price"]:
        errors.setdefault("price", []).append(
            f"{tier_label} packages must be priced at least RWF {rules['min_price']:,.0f}."
        )
    if clean_description and len(clean_description) < rules["min_description_length"]:
        errors.setdefault("description", []).append(
            f"{tier_label} packages must include at least {rules['min_description_length']} characters explaining deliverables and terms."
        )

    lowered_name = clean_name.lower()
    if has_control_characters(clean_description):
        errors.setdefault("description", []).append("Control characters are not allowed.")
    if tier == "standard" and any(term in lowered_name for term in RESTRICTED_STANDARD_TERMS):
        errors.setdefault("name", []).append("Standard packages cannot claim premium, exclusive, VIP, or Gold positioning.")
    if tier == "gold" and any(term in f"{lowered_name} {clean_description.lower()}" for term in MISLEADING_GUARANTEE_TERMS):
        errors.setdefault("description", []).append("Gold packages must avoid misleading guarantee claims.")

    if errors:
        raise PackageValidationError(field_errors=errors)


def coerce_package_price(value) -> Decimal:
    try:
        price = positive_decimal(value)
    except ValueError:
        raise ValueError("Package price must be a valid decimal amount.")
    return price


def _to_decimal(value) -> Decimal | None:
    try:
        return Decimal(str(value))
    except (InvalidOperation, TypeError, ValueError):
        return None

from dataclasses import dataclass
from datetime import datetime, timedelta
from decimal import Decimal
from types import MappingProxyType
from typing import Mapping
from typing import Optional

from domain.vendors.packages.errors import PackageValidationError
from domain.vendors.shared.aggregate import VendorDomainError
# coerce_package_price is defined above in this module
from domain.vendors.shared.validation import aware_utc_datetime, bounded_text, normalize_currency

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
    if price is not None:
        try:
            normalized_price = coerce_package_price(price)
        except ValueError as exc:
            raise PackageValidationError(field_errors={"price": [str(exc)]}) from exc
        if normalized_price != package.price:
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


def package_public_edit_markers(package, *, now: datetime, public_fields_changed: bool) -> Mapping[str, object]:
    now = _normalize_timestamp(now, "now", required=True)
    if not public_fields_changed:
        return MappingProxyType({})
    ensure_vendor_package_edit_allowed(package, public_fields_changed=True, now=now)
    return MappingProxyType(
        {
            "approval_status": "waiting_approval",
            "rejection_reason": None,
            "is_active": False,
            "last_vendor_public_edit_at": now,
            "next_vendor_edit_allowed_at": now + VENDOR_PACKAGE_EDIT_COOLDOWN,
        }
    )


def mark_vendor_package_public_edit(package, *, now: datetime, public_fields_changed: bool) -> Mapping[str, object]:
    return package_public_edit_markers(package, now=now, public_fields_changed=public_fields_changed)


def _normalize_public_text(value: str) -> str:
    return bounded_text(value, field_name="public_field", max_length=5000).strip()


def _normalize_timestamp(value, field_name: str, *, required: bool = False):
    try:
        return aware_utc_datetime(value, field_name=field_name, required=required)
    except ValueError as exc:
        raise PackageValidationError(field_errors={field_name: [str(exc)]}) from exc
