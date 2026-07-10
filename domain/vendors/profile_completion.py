from __future__ import annotations

from typing import Any

from domain.vendors.validation import MIN_VENDOR_DESCRIPTION_LENGTH

REQUIRED_VENDOR_PROFILE_FIELDS = (
    "business_name",
    "category",
    "description",
    "service_area",
    "contact_email",
    "contact_phone",
)


def get_vendor_profile_completion_errors(profile: object | None) -> dict[str, list[str]]:
    """Return profile-completion errors for domain, DTO, or persistence projections."""
    if profile is None:
        return {}

    errors: dict[str, list[str]] = {}
    for field_name in REQUIRED_VENDOR_PROFILE_FIELDS:
        value = getattr(profile, field_name, None)
        if value is None or not str(value).strip():
            errors[field_name] = ["This field is required."]

    description = getattr(profile, "description", None)
    if description and len(str(description).strip()) < MIN_VENDOR_DESCRIPTION_LENGTH:
        errors["description"] = [
            f"Use at least {MIN_VENDOR_DESCRIPTION_LENGTH} characters for your description."
        ]

    category = getattr(profile, "category", None)
    category_value: Any = getattr(category, "value", category)
    custom_category = getattr(profile, "custom_category", None)
    if str(category_value or "").strip().lower() == "other" and not str(
        custom_category or ""
    ).strip():
        errors["custom_category"] = [
            "Tell us what service you provide when choosing Other."
        ]

    return errors
