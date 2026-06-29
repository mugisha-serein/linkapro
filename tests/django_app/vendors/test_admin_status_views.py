import pytest
from django.urls import reverse
from rest_framework.test import APIClient

from django_app.identity.models import User
from django_app.vendors.models import VendorProfile


pytestmark = pytest.mark.django_db


def _user(email: str, role: str) -> User:
    return User.objects.create_user(
        email=email,
        password="pass123",
        first_name=role.title(),
        last_name="User",
        role=role,
        is_active=True,
        is_verified=True,
    )


def _vendor_profile(status: str = "pending_review") -> VendorProfile:
    return VendorProfile.objects.create(
        user=_user("vendor-status@example.com", "vendor"),
        business_name="Status Vendor",
        category="photography",
        description="A complete vendor description for status transitions.",
        service_area="Kigali, Rwanda",
        contact_email="status@example.com",
        contact_phone="+250700000000",
        status=status,
    )


def _admin_client() -> APIClient:
    client = APIClient()
    client.force_authenticate(user=_user("admin-status@example.com", "admin"))
    return client


def test_admin_can_approve_pending_vendor():
    profile = _vendor_profile("pending_review")
    response = _admin_client().post(reverse("admin-vendor-approve", args=[profile.id]))

    assert response.status_code == 200
    profile.refresh_from_db()
    assert profile.status == "approved"
    assert response.data["code"] == "vendor_approve_completed"
    assert response.data["data"]["status"] == "approved"


def test_admin_can_reject_pending_vendor_with_reason():
    profile = _vendor_profile("pending_review")
    response = _admin_client().post(
        reverse("admin-vendor-reject", args=[profile.id]),
        {"reason": "Documents are not clear enough."},
        format="json",
    )

    assert response.status_code == 200
    profile.refresh_from_db()
    assert profile.status == "rejected"
    assert profile.rejection_reason == "Documents are not clear enough."
    assert response.data["code"] == "vendor_reject_completed"


def test_admin_can_suspend_approved_vendor():
    profile = _vendor_profile("approved")
    response = _admin_client().post(reverse("admin-vendor-suspend", args=[profile.id]))

    assert response.status_code == 200
    profile.refresh_from_db()
    assert profile.status == "suspended"
    assert response.data["code"] == "vendor_suspend_completed"


def test_admin_can_reinstate_suspended_vendor():
    profile = _vendor_profile("suspended")
    response = _admin_client().post(reverse("admin-vendor-reinstate", args=[profile.id]))

    assert response.status_code == 200
    profile.refresh_from_db()
    assert profile.status == "approved"
    assert response.data["code"] == "vendor_reinstate_completed"


def test_vendor_user_cannot_call_admin_vendor_status_endpoint():
    profile = _vendor_profile("pending_review")
    client = APIClient()
    client.force_authenticate(user=profile.user)

    response = client.post(reverse("admin-vendor-approve", args=[profile.id]))

    assert response.status_code == 403
    profile.refresh_from_db()
    assert profile.status == "pending_review"
