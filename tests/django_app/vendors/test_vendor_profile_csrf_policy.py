import pytest
from django.urls import resolve, reverse
from rest_framework.test import APIClient

from django_app.identity.models import User


pytestmark = pytest.mark.django_db


def _vendor_user():
    return User.objects.create_user(
        email="csrf-vendor@example.com",
        password="pass123",
        first_name="Vendor",
        last_name="User",
        role="vendor",
    )


def _profile_payload():
    return {
        "business_name": "CSRF Safe Studio",
        "category": "photography",
        "description": "Professional photography services for weddings and events.",
        "service_area": "Kigali, Rwanda",
        "contact_email": "studio@example.com",
        "contact_phone": "+250788123456",
    }


def test_vendor_profile_route_is_not_marked_csrf_exempt():
    resolved = resolve(reverse("vendor-profile"))

    assert getattr(resolved.func, "csrf_exempt", False) is False


def test_vendor_profile_create_requires_csrf_for_authenticated_browser_requests():
    client = APIClient(enforce_csrf_checks=True)
    client.force_authenticate(user=_vendor_user())

    response = client.post(reverse("vendor-profile"), _profile_payload(), format="json")

    assert response.status_code == 403
