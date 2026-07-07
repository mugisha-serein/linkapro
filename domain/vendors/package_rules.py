from decimal import Decimal, InvalidOperation

from domain.vendors.errors import PackageValidationError
from domain.vendors.validation import (
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
    "standard": {"min_price": Decimal("1"), "min_description_length": 10},
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
            f"{tier_label} packages must include at least "
            f"{rules['min_description_length']} characters explaining deliverables and terms."
        )

    lowered_name = clean_name.lower()
    if has_control_characters(clean_description):
        errors.setdefault("description", []).append("Control characters are not allowed.")
    if tier == "standard" and any(term in lowered_name for term in RESTRICTED_STANDARD_TERMS):
        errors.setdefault("name", []).append(
            "Standard packages cannot claim premium, exclusive, VIP, or Gold positioning."
        )
    if tier == "gold" and any(
        term in f"{lowered_name} {clean_description.lower()}" for term in MISLEADING_GUARANTEE_TERMS
    ):
        errors.setdefault("description", []).append("Gold packages must avoid misleading guarantee claims.")

    if errors:
        raise PackageValidationError(field_errors=errors)


def coerce_package_price(value) -> Decimal:
    try:
        price = positive_decimal(value)
    except ValueError as exc:
        raise ValueError("Package price must be a valid decimal amount.")
    return price


def _to_decimal(value) -> Decimal | None:
    try:
        return Decimal(str(value))
    except (InvalidOperation, TypeError, ValueError):
        return None
