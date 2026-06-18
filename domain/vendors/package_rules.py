from decimal import Decimal, InvalidOperation


class PackageValidationError(ValueError):
    def __init__(self, errors: dict[str, list[str]]):
        self.errors = errors
        super().__init__("Service package validation failed.")


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
        raise PackageValidationError(errors)

    clean_name = (name or "").strip()
    clean_description = (description or "").strip()
    price_value = _to_decimal(price)
    tier_label = PACKAGE_TIER_LABELS[tier]

    if not clean_name:
        errors.setdefault("name", []).append("Package name is required.")
    if price_value is None or price_value <= 0:
        errors.setdefault("price", []).append("Package price must be greater than 0.")
    elif price_value < rules["min_price"]:
        errors.setdefault("price", []).append(
            f"{tier_label} packages must be priced at least RWF {rules['min_price']:,.0f}."
        )
    if len(clean_description) < rules["min_description_length"]:
        errors.setdefault("description", []).append(
            f"{tier_label} packages must include at least {rules['min_description_length']} characters explaining deliverables and terms."
        )

    lowered_name = clean_name.lower()
    if tier == "standard" and any(term in lowered_name for term in RESTRICTED_STANDARD_TERMS):
        errors.setdefault("name", []).append("Standard packages cannot claim premium, exclusive, VIP, or Gold positioning.")
    if tier == "gold" and any(term in f"{lowered_name} {clean_description.lower()}" for term in MISLEADING_GUARANTEE_TERMS):
        errors.setdefault("description", []).append("Gold packages must avoid misleading guarantee claims.")

    if errors:
        raise PackageValidationError(errors)


def _to_decimal(value) -> Decimal | None:
    try:
        return Decimal(str(value))
    except (InvalidOperation, TypeError, ValueError):
        return None
