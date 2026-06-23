import pytest
from django.urls import reverse
from rest_framework.test import APIClient

from django_app.vendors.models import Inquiry, PortfolioImage, ServicePackage, VerificationDocument
from tests.factories import create_portfolio_image, create_service_package, create_vendor_profile

pytestmark = pytest.mark.django_db


@pytest.fixture
def client():
    return APIClient()


@pytest.mark.parametrize("vendor_status", ["draft", "pending_review", "rejected", "suspended"])
def test_unapproved_vendor_public_profile_returns_404(client, vendor_status):
    vendor = create_vendor_profile(status=vendor_status)

    response = client.get(reverse("public-vendor-profile", args=[vendor.id]))

    assert response.status_code == 404


def test_approved_public_profile_only_exposes_public_media_and_packages(client):
    vendor = create_vendor_profile(status="approved", category="other", custom_category="Wedding stationery")
    public_image = create_portfolio_image(
        vendor=vendor,
        secure_url="https://cdn.example.com/fallback.jpg",
        cloudinary_secure_url="https://cdn.example.com/public.jpg",
        upload_status=PortfolioImage.UploadStatus.UPLOADED,
        quality_status=PortfolioImage.QualityStatus.PASSED,
        visibility_status=PortfolioImage.VisibilityStatus.APPROVED,
        is_active=True,
    )
    create_portfolio_image(
        vendor=vendor,
        secure_url="",
        cloudinary_secure_url=None,
        local_preview_url="https://local.example.com/private.jpg",
        temp_upload_path="vendor_portfolio_uploads/private.jpg",
        upload_status=PortfolioImage.UploadStatus.STAGED,
        quality_status=PortfolioImage.QualityStatus.PENDING_ANALYSIS,
        visibility_status=PortfolioImage.VisibilityStatus.PRIVATE,
    )
    deleted_image = create_portfolio_image(vendor=vendor, secure_url="https://cdn.example.com/deleted.jpg")
    deleted_image.soft_delete()

    approved_package = create_service_package(
        vendor=vendor,
        approval_status=ServicePackage.ApprovalStatus.APPROVED,
        is_active=True,
    )
    create_service_package(vendor=vendor, approval_status=ServicePackage.ApprovalStatus.REJECTED)
    create_service_package(vendor=vendor, approval_status=ServicePackage.ApprovalStatus.APPROVED, is_active=False)
    deleted_package = create_service_package(vendor=vendor, approval_status=ServicePackage.ApprovalStatus.APPROVED)
    deleted_package.soft_delete()
    VerificationDocument.objects.create(
        vendor=vendor,
        document_type=VerificationDocument.DocumentType.BUSINESS_REGISTRATION,
        original_filename="private.pdf",
        secure_url="https://cdn.example.com/private-document.pdf",
    )

    response = client.get(reverse("public-vendor-profile", args=[vendor.id]))

    assert response.status_code == 200
    assert response.data["success"] is True
    assert response.data["code"] == "vendor_public_profile_loaded"
    profile = response.data["data"]
    assert profile["category_label"] == "Other"
    assert profile["custom_category"] == "Wedding stationery"
    assert profile["cover_image_url"] == "https://cdn.example.com/public.jpg"
    assert [item["id"] for item in profile["portfolio"]] == [str(public_image.id)]
    assert profile["portfolio"][0]["display_url"] == "https://cdn.example.com/public.jpg"
    assert [item["id"] for item in profile["packages"]] == [str(approved_package.id)]
    serialized = str(response.data)
    assert "private-document.pdf" not in serialized
    assert "temp_upload_path" not in serialized
    assert "local_preview_url" not in serialized
    assert "vendor_portfolio_uploads/private.jpg" not in serialized


def test_public_inquiry_requires_approved_vendor(client):
    vendor = create_vendor_profile(status="pending_review")

    response = client.post(
        reverse("public-inquiries", args=[vendor.id]),
        {"client_name": "Client", "client_email": "client@example.com", "message": "Please share your availability."},
        format="json",
    )

    assert response.status_code == 404
    assert Inquiry.objects.count() == 0


def test_public_inquiry_creates_record_for_approved_vendor(client):
    vendor = create_vendor_profile(status="approved")

    response = client.post(
        reverse("public-inquiries", args=[vendor.id]),
        {
            "client_name": "Client",
            "client_email": "client@example.com",
            "client_phone": "+250788000000",
            "message": "Please share your availability for our wedding.",
            "event_date": "2027-08-20",
        },
        format="json",
    )

    assert response.status_code == 201
    assert response.data["code"] == "vendor_inquiry_created"
    inquiry = Inquiry.objects.get(vendor=vendor)
    assert inquiry.client_email == "client@example.com"
