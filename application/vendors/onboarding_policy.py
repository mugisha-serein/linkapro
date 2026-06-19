from __future__ import annotations

from typing import Any


SETUP_ROUTE = "/vendor/profile/setup"
DASHBOARD_ROUTE = "/vendor/dashboard"


def build_vendor_onboarding_contract(profile: Any | None) -> dict[str, Any]:
    if profile is None:
        return {
            "profile_status": "missing",
            "can_access_dashboard": False,
            "must_complete_profile": True,
            "can_submit_for_review": False,
            "marketplace_visible": False,
            "redirect_to": SETUP_ROUTE,
            "message": "Complete your vendor profile before continuing.",
        }

    status = str(getattr(profile, "status", "draft") or "draft")
    field_errors = _profile_completion_errors(profile)
    is_complete = not field_errors

    if status == "approved":
        return {
            "profile_status": status,
            "can_access_dashboard": True,
            "must_complete_profile": False,
            "can_submit_for_review": False,
            "marketplace_visible": True,
            "redirect_to": DASHBOARD_ROUTE,
            "message": "Your vendor profile is approved and visible in the marketplace.",
        }

    if status == "pending_review":
        return {
            "profile_status": status,
            "can_access_dashboard": True,
            "must_complete_profile": False,
            "can_submit_for_review": False,
            "marketplace_visible": False,
            "redirect_to": DASHBOARD_ROUTE,
            "message": "Your profile is under review. Marketplace visibility starts after admin approval.",
        }

    if status == "suspended":
        return {
            "profile_status": status,
            "can_access_dashboard": False,
            "must_complete_profile": False,
            "can_submit_for_review": False,
            "marketplace_visible": False,
            "redirect_to": SETUP_ROUTE,
            "message": "Your vendor account is suspended. Please contact support.",
        }

    if status == "rejected":
        return {
            "profile_status": status,
            "can_access_dashboard": False,
            "must_complete_profile": True,
            "can_submit_for_review": is_complete,
            "marketplace_visible": False,
            "redirect_to": SETUP_ROUTE,
            "message": getattr(profile, "rejection_reason", None)
            or "Your vendor profile needs updates before resubmission.",
        }

    incomplete_status = "incomplete" if not is_complete else status
    return {
        "profile_status": incomplete_status,
        "can_access_dashboard": False,
        "must_complete_profile": True,
        "can_submit_for_review": is_complete,
        "marketplace_visible": False,
        "redirect_to": SETUP_ROUTE,
        "message": "Complete your vendor profile before continuing."
        if not is_complete
        else "Submit your vendor profile for admin review.",
    }


def vendor_field_errors(profile: Any | None) -> dict[str, list[str]]:
    if profile is None:
        return {}
    return _profile_completion_errors(profile)


def _profile_completion_errors(profile: Any) -> dict[str, list[str]]:
    if hasattr(profile, "get_profile_completion_errors"):
        return profile.get_profile_completion_errors()

    errors: dict[str, list[str]] = {}
    for field_name in (
        "business_name",
        "category",
        "description",
        "service_area",
        "contact_email",
        "contact_phone",
    ):
        value = getattr(profile, field_name, None)
        if value is None or not str(value).strip():
            errors[field_name] = ["This field is required."]

    description = getattr(profile, "description", None)
    if description and len(str(description).strip()) < 20:
        errors["description"] = ["Use at least 20 characters for your description."]

    category = getattr(profile, "category", None)
    category_value = getattr(category, "value", category)
    if category_value == "other" and not (getattr(profile, "custom_category", None) or "").strip():
        errors["custom_category"] = ["Tell us what service you provide when choosing Other."]

    return errors
