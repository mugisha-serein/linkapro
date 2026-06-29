import uuid

import pytest
from django.core.files.uploadedfile import SimpleUploadedFile
from django.urls import reverse
from rest_framework.test import APIClient

from django_app.identity.models import User
from django_app.vendors.models import ServicePackage, VendorProfile


pytestmark = pytest.mark.django_db


@pytest.fixture
def vendor_client():
    client = APIClient()
    user = User.objects.create_user(
        email="contracts-vendor@example.com",
        password="pass123",
        first_name="Vendor",
        last_name="User",
        role="vendor",
    )
    profile = VendorProfile.objects.create(
        user=user,
        business_name="Contract Vendor",
        category="photography",
        description="A complete vendor description.",
        service_area="Kigali",
        contact_email="vendor@example.com",
        contact_phone="+250788123456",
        status=VendorProfile.Status.PENDING_REVIEW,
    )
    client.force_authenticate(user=user)
    return client, profile


def test_vendor_profile_status_includes_contract_metadata(vendor_client):
    client, _ = vendor_client

    response = client.get(reverse("vendor-profile-status"))

    assert response.status_code == 200
    assert response.data["success"] is True
    assert response.data["code"] == "vendor_profile_status_loaded"
    assert response.data["message"] == "Vendor profile status loaded."
    assert "profile" in response.data
    assert "onboarding" in response.data


def test_portfolio_missing_item_uses_structured_error_contract(vendor_client):
    client, _ = vendor_client

    response = client.delete(reverse("portfolio-detail", args=[uuid.uuid4()]))

    assert response.status_code == 404
    assert response.data["success"] is False
    assert response.data["code"] == "vendor_portfolio_item_not_found"
    assert response.data["message"] == "Image not found or does not belong to this vendor."
    assert response.data["detail"] == response.data["message"]
    assert response.data["field_errors"] == {}


def test_package_missing_item_uses_structured_error_contract(vendor_client):
    client, _ = vendor_client

    response = client.patch(
        reverse("package-detail", args=[uuid.uuid4()]),
        {
            "name": "Updated package",
            "description": "Updated package description.",
            "price": "2500.00",
            "currency": "RWF",
            "package_tier": "standard",
        },
        format="json",
    )

    assert response.status_code == 404
    assert response.data["success"] is False
    assert response.data["code"] == "vendor_package_not_found"
    assert response.data["message"] == "Package not found or does not belong to this vendor."
    assert response.data["field_errors"] == {}


def test_package_remove_success_includes_contract_metadata(vendor_client):
    client, profile = vendor_client
    package = ServicePackage.objects.create(
        vendor=profile,
        name="Basic Package",
        description="Package description.",
        price="1000.00",
        currency="RWF",
        package_tier="standard",
        approval_status=ServicePackage.ApprovalStatus.APPROVED,
        is_active=True,
    )

    response = client.delete(reverse("package-detail", args=[package.id]))

    assert response.status_code == 200
    assert response.data["success"] is True
    assert response.data["code"] == "vendor_package_removed"
    assert response.data["message"] == "Package removed from active listings."
    assert "package" in response.data


def test_package_activate_uses_structured_admin_approval_error(vendor_client):
    client, _ = vendor_client

    response = client.post(reverse("package-activate", args=[uuid.uuid4()]))

    assert response.status_code == 403
    assert response.data["success"] is False
    assert response.data["code"] == "vendor_package_admin_approval_required"
    assert response.data["message"] == "Package publication requires admin approval."
    assert response.data["detail"] == "Package publication requires admin approval."
    assert response.data["field_errors"] == {}


def test_verification_document_error_preserves_field_and_adds_contract(vendor_client):
    client, _ = vendor_client
    document_file = SimpleUploadedFile("license.png", b"invalid", content_type="image/png")

    response = client.post(
        reverse("vendor-verification-documents"),
        {"document_type": "trade_license", "document": document_file},
        format="multipart",
    )

    assert response.status_code == 400
    assert "document" in response.data
    assert response.data["success"] is False
    assert response.data["code"] == "vendor_verification_document_invalid"
    assert response.data["message"] == "Upload a valid verification PDF."
    assert response.data["field_errors"] == {"document": response.data["document"]}
