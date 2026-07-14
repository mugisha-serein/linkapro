from __future__ import annotations

import uuid

from domain.vendors.profile.rules import get_profile_completion_errors
from django_app.vendors.models import VendorProfile as DjangoVendorProfile
from infrastructure.repos.analytics import metrics

PROFILE_STRENGTH_LOW = "profile_strength_low"
NO_ACTIVE_PACKAGES = "no_active_packages"
RESPONSE_RATE_LOW = "response_rate_low"

PROFILE_STRENGTH_LOW_THRESHOLD = 60
RESPONSE_RATE_LOW_THRESHOLD = 50

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


def optimization_alerts(vendor_id: uuid.UUID) -> tuple[str, ...]:
    alerts: list[str] = []
    if metrics.profile_strength_score(vendor_id) < PROFILE_STRENGTH_LOW_THRESHOLD:
        alerts.append(PROFILE_STRENGTH_LOW)
    if metrics.active_packages_count(vendor_id) == 0:
        alerts.append(NO_ACTIVE_PACKAGES)
    if metrics.response_rate(vendor_id) < RESPONSE_RATE_LOW_THRESHOLD:
        alerts.append(RESPONSE_RATE_LOW)
    return tuple(alerts)
