import pytest
from django.urls import resolve, reverse
from rest_framework.test import APIClient

from django_app.identity.models import User


pytestmark = pytest.mark.django_db


def _user(email: str, role: str):
    return User.objects.create_user(
        email=email,
        password="pass123",
        first_name="Test",
        last_name="User",
        role=role,
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


def test_vendor_profile_route_uses_drf_csrf_exempt_view():
    resolved = resolve(reverse("vendor-profile"))

    assert getattr(resolved.func, "csrf_exempt", False) is True


def test_vendor_profile_create_allows_authenticated_vendor_without_csrf_cookie():
    client = APIClient(enforce_csrf_checks=True)
    client.force_authenticate(user=_user("csrf-vendor@example.com", "vendor"))

    response = client.post(reverse("vendor-profile"), _profile_payload(), format="json")

    assert response.status_code == 201
    assert response.data["business_name"] == "CSRF Safe Studio"


def test_vendor_profile_create_rejects_unauthenticated_request_without_csrf_cookie():
    client = APIClient(enforce_csrf_checks=True)

    response = client.post(reverse("vendor-profile"), _profile_payload(), format="json")

    assert response.status_code in {401, 403}


def test_vendor_profile_create_rejects_planner_without_csrf_cookie():
    client = APIClient(enforce_csrf_checks=True)
    client.force_authenticate(user=_user("csrf-planner@example.com", "planner"))

    response = client.post(reverse("vendor-profile"), _profile_payload(), format="json")

    assert response.status_code == 403
