from datetime import timedelta

import pytest
from django.urls import reverse
from django.utils import timezone
from rest_framework.test import APIClient

from django_app.identity.models import User
from django_app.vendors.models import ServicePackage, VendorProfile


pytestmark = pytest.mark.django_db


def create_vendor_with_approved_package(*, approved_at=None, next_allowed_at=None):
    client = APIClient()
    user = User.objects.create_user(
        email="cooldown-vendor@example.com",
        password="pass123",
        role="vendor",
    )
    client.force_authenticate(user=user)
    vendor = VendorProfile.objects.create(
        user=user,
        business_name="Cooldown Vendor",
        category="photography",
        description="A complete vendor description.",
        service_area="Kigali",
        contact_email="vendor@example.com",
        contact_phone="+250788123456",
        status=VendorProfile.Status.APPROVED,
        approved_at=timezone.now() - timedelta(days=20),
    )
    approved_at = approved_at or timezone.now() - timedelta(days=1)
    package = ServicePackage.objects.create(
        vendor=vendor,
        name="Approved Package",
        description="A package that was already approved by admin.",
        price="100000.00",
        currency="RWF",
        package_tier="standard",
        approval_status=ServicePackage.ApprovalStatus.APPROVED,
        is_active=True,
        last_approved_at=approved_at,
        next_vendor_edit_allowed_at=next_allowed_at or approved_at + ServicePackage.vendor_edit_cooldown_delta(),
    )
    return client, package


def test_approved_package_update_is_blocked_until_cooldown_passes():
    client, package = create_vendor_with_approved_package()

    response = client.patch(
        reverse("package-detail", args=[package.id]),
        {"name": "Updated Package"},
        format="json",
    )

    package.refresh_from_db()
    assert response.status_code == 429
    assert response.data["success"] is False
    assert response.data["code"] == "vendor_package_edit_cooldown_active"
    assert response.data["cooldown_days"] == 15
    assert response.data["next_allowed_at"] == package.next_vendor_edit_allowed_at.isoformat()
    assert package.name == "Approved Package"
    assert package.approval_status == ServicePackage.ApprovalStatus.APPROVED
    assert package.is_active is True


def test_package_update_after_cooldown_moves_package_back_to_admin_review():
    approved_at = timezone.now() - ServicePackage.vendor_edit_cooldown_delta() - timedelta(minutes=1)
    next_allowed_at = approved_at + ServicePackage.vendor_edit_cooldown_delta()
    client, package = create_vendor_with_approved_package(
        approved_at=approved_at,
        next_allowed_at=next_allowed_at,
    )

    response = client.patch(
        reverse("package-detail", args=[package.id]),
        {"name": "Updated Package"},
        format="json",
    )

    package.refresh_from_db()
    assert response.status_code == 200
    assert response.data["success"] is True
    assert response.data["code"] == "vendor_package_updated"
    assert response.data["approval_status"] == ServicePackage.ApprovalStatus.WAITING_APPROVAL
    assert response.data["is_active"] is False
    assert response.data["last_vendor_public_edit_at"] == package.last_vendor_public_edit_at.isoformat()
    assert response.data["next_vendor_edit_allowed_at"] == package.next_vendor_edit_allowed_at.isoformat()
    assert response.data["can_edit_now"] is False
    assert package.name == "Updated Package"
    assert package.approval_status == ServicePackage.ApprovalStatus.WAITING_APPROVAL
    assert package.is_active is False
    assert package.last_vendor_public_edit_at is not None
    assert package.next_vendor_edit_allowed_at > timezone.now()


def test_package_list_exposes_cooldown_metadata():
    client, package = create_vendor_with_approved_package()

    response = client.get(reverse("package-list"))

    assert response.status_code == 200
    assert response.data[0]["id"] == str(package.id)
    assert response.data[0]["can_edit_now"] is False
    assert response.data[0]["package_edit_cooldown_days"] == 15
    assert response.data[0]["next_vendor_edit_allowed_at"] == package.next_vendor_edit_allowed_at.isoformat()


def test_admin_package_approval_starts_vendor_edit_cooldown():
    admin_user = User.objects.create_superuser("package-admin@example.com", "pass")
    client = APIClient()
    client.force_authenticate(user=admin_user)
    vendor_user = User.objects.create_user(email="pending-package-vendor@example.com", password="p", role="vendor")
    vendor = VendorProfile.objects.create(
        user=vendor_user,
        business_name="Pending Package Vendor",
        category="photography",
        description="A complete vendor description.",
        service_area="Kigali",
        contact_email="pending@example.com",
        contact_phone="+250788123456",
        status=VendorProfile.Status.APPROVED,
    )
    package = ServicePackage.objects.create(
        vendor=vendor,
        name="Pending Package",
        description="A package waiting for admin approval.",
        price="100000.00",
        currency="RWF",
        package_tier="standard",
        approval_status=ServicePackage.ApprovalStatus.WAITING_APPROVAL,
        is_active=False,
    )

    response = client.post(reverse("admin-vendor-package-approve", args=[package.id]))

    package.refresh_from_db()
    assert response.status_code == 200
    assert package.approval_status == ServicePackage.ApprovalStatus.APPROVED
    assert package.is_active is True
    assert package.last_approved_at is not None
    assert package.next_vendor_edit_allowed_at == package.last_approved_at + ServicePackage.vendor_edit_cooldown_delta()
    assert response.data["package"]["next_vendor_edit_allowed_at"] == package.next_vendor_edit_allowed_at.isoformat()
    assert response.data["package"]["can_edit_now"] is False
