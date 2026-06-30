import pytest
from django.urls import reverse
from rest_framework.test import APIClient

from django_app.identity.models import User
from django_app.vendors.models import ServicePackage, VendorProfile


pytestmark = pytest.mark.django_db


def create_vendor(email):
    user = User.objects.create_user(email=email, password="pass123", role="vendor")
    vendor = VendorProfile.objects.create(
        user=user,
        business_name="Vendor Business",
        category="photography",
        description="A complete vendor description.",
        service_area="Kigali",
        contact_email=email,
        contact_phone="+250788123456",
        status=VendorProfile.Status.PENDING_REVIEW,
    )
    return user, vendor


def create_package(vendor):
    return ServicePackage.objects.create(
        vendor=vendor,
        name="Owned Package",
        description="A package owned by the first vendor.",
        price="100000.00",
        currency="RWF",
        package_tier="standard",
        approval_status=ServicePackage.ApprovalStatus.WAITING_APPROVAL,
        is_active=False,
    )


def authenticated_client(user):
    client = APIClient()
    client.force_authenticate(user=user)
    return client


def test_vendor_can_update_own_package_after_command_receives_vendor_id():
    user, vendor = create_vendor("owner@example.com")
    package = create_package(vendor)
    client = authenticated_client(user)

    response = client.patch(
        reverse("package-detail", args=[package.id]),
        {"name": "Updated Owned Package"},
        format="json",
    )

    package.refresh_from_db()
    assert response.status_code == 200
    assert response.data["success"] is True
    assert response.data["code"] == "vendor_package_updated"
    assert package.name == "Updated Owned Package"


def test_vendor_cannot_update_another_vendor_package():
    _, owner_vendor = create_vendor("owner2@example.com")
    other_user, _ = create_vendor("other@example.com")
    package = create_package(owner_vendor)
    client = authenticated_client(other_user)

    response = client.patch(
        reverse("package-detail", args=[package.id]),
        {"name": "Illegal Update"},
        format="json",
    )

    package.refresh_from_db()
    assert response.status_code == 404
    assert response.data["success"] is False
    assert response.data["code"] == "vendor_package_not_found"
    assert package.name == "Owned Package"


def test_vendor_can_delete_own_package_after_command_receives_vendor_id():
    user, vendor = create_vendor("delete-owner@example.com")
    package = create_package(vendor)
    client = authenticated_client(user)

    response = client.delete(reverse("package-detail", args=[package.id]))

    package = ServicePackage.all_objects.get(id=package.id)
    assert response.status_code == 200
    assert response.data["success"] is True
    assert response.data["code"] == "vendor_package_removed"
    assert package.is_deleted is True
    assert package.is_active is False
    assert package.deleted_by == user


def test_vendor_cannot_delete_another_vendor_package():
    _, owner_vendor = create_vendor("delete-owner2@example.com")
    other_user, _ = create_vendor("delete-other@example.com")
    package = create_package(owner_vendor)
    client = authenticated_client(other_user)

    response = client.delete(reverse("package-detail", args=[package.id]))

    package.refresh_from_db()
    assert response.status_code == 404
    assert response.data["success"] is False
    assert response.data["code"] == "vendor_package_not_found"
    assert package.is_deleted is False
    assert package.is_active is False
