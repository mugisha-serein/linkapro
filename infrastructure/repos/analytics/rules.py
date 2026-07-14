from __future__ import annotations

import uuid

from domain.vendors.profile.rules import get_profile_completion_errors
from django_app.vendors.models import VendorProfile as DjangoVendorProfile

_PROFILE_STRENGTH_SUGGESTIONS = {
    "business_name": "Add your business name so clients can recognize your brand.",
    "category": "Choose the service category that best describes your business.",
    "custom_category": "Describe your service when choosing Other as your category.",
    "description": "Write a stronger business description with at least 20 characters.",
    "service_area": "Add the area where you provide services.",
    "contact_email": "Add a contact email for client inquiries.",
    "contact_phone": "Add a contact phone number for client inquiries.",
}


def _suggestions_for_completion_errors(errors: dict[str, list[str]]) -> dict[str, str]:
    return {
        field_name: _PROFILE_STRENGTH_SUGGESTIONS.get(
            field_name,
            f"Update {field_name.replace('_', ' ')} to strengthen your profile.",
        )
        for field_name in errors
    }


def profile_strength_suggestions(vendor_id: uuid.UUID) -> dict[str, str]:
    profile = DjangoVendorProfile.objects.get(id=vendor_id)
    return _suggestions_for_completion_errors(get_profile_completion_errors(profile))
