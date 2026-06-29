import pytest
from django.urls import reverse
from rest_framework.test import APIClient

from application.governance.commands import ApproveVendorCommand
from django_app.governance.models import AuditLog
from django_app.governance.services import get_command_handlers
from django_app.identity.models import User
from django_app.vendors.models import PortfolioImage, ServicePackage, VendorProfile


pytestmark = pytest.mark.django_db


def create_pending_vendor(email="pending-unified@example.com"):
    vendor_user = User.objects.create_user(email=email, password="p", role="vendor")
    return VendorProfile.objects.create(
        user=vendor_user,
        business_name="Pending Unified Vendor",
        category="photography",
        description="A complete vendor description for approval.",
        service_area="Kigali",
        contact_email="vendor@example.com",
        contact_phone="+250788123456",
        status=VendorProfile.Status.PENDING_REVIEW,
    )


def add_pending_package(vendor):
    return ServicePackage.objects.create(
        vendor=vendor,
        name="Wedding Photo Package",
        description="A complete wedding photography package awaiting review.",
        price="150000.00",
        currency="RWF",
        package_tier="standard",
        approval_status=ServicePackage.ApprovalStatus.WAITING_APPROVAL,
        is_active=False,
    )


def add_portfolio_item(vendor, *, secure_url, quality_status=PortfolioImage.QualityStatus.PASSED):
    return PortfolioImage.objects.create(
        vendor=vendor,
        media_type=PortfolioImage.MediaType.IMAGE,
        public_id="portfolio/item",
        secure_url=secure_url,
        upload_status=PortfolioImage.UploadStatus.UPLOADED,
        quality_status=quality_status,
        visibility_status=PortfolioImage.VisibilityStatus.WAITING_APPROVAL,
        is_active=True,
    )


def test_admin_vendor_approval_approves_profile_packages_and_safe_portfolio(monkeypatch):
    synced = []
    monkeypatch.setattr(
        "django_app.governance.views.sync_vendor_to_marketplace",
        lambda vendor: synced.append(vendor) or {"status": "ok"},
    )
    admin_user = User.objects.create_superuser("unified-admin@example.com", "pass")
    api_client = APIClient()
    api_client.force_authenticate(user=admin_user)
    vendor = create_pending_vendor()
    package = add_pending_package(vendor)
    safe_media = add_portfolio_item(vendor, secure_url="https://cdn.example.com/portfolio.jpg")
    unsafe_media = add_portfolio_item(vendor, secure_url="/media/vendor_portfolio_uploads/private.jpg")
    failed_media = add_portfolio_item(
        vendor,
        secure_url="https://cdn.example.com/failed.jpg",
        quality_status=PortfolioImage.QualityStatus.FAILED,
    )

    response = api_client.post(reverse("admin-vendor-approve", args=[vendor.id]))

    vendor.refresh_from_db()
    package.refresh_from_db()
    safe_media.refresh_from_db()
    unsafe_media.refresh_from_db()
    failed_media.refresh_from_db()
    assert response.status_code == 200
    assert vendor.status == VendorProfile.Status.APPROVED
    assert package.approval_status == ServicePackage.ApprovalStatus.APPROVED
    assert package.is_active is True
    assert safe_media.visibility_status == PortfolioImage.VisibilityStatus.APPROVED
    assert unsafe_media.visibility_status == PortfolioImage.VisibilityStatus.WAITING_APPROVAL
    assert failed_media.visibility_status == PortfolioImage.VisibilityStatus.WAITING_APPROVAL
    assert response.data["approval_summary"] == {
        "packages_approved": 1,
        "portfolio_items_approved": 1,
        "portfolio_items_skipped": 1,
    }
    assert synced and synced[0].id == vendor.id
    audit = AuditLog.objects.get(action_type=AuditLog.ActionType.APPROVE_VENDOR, target_id=vendor.id)
    assert audit.details == response.data["approval_summary"]


def test_governance_command_handler_uses_unified_vendor_approval(monkeypatch):
    monkeypatch.setattr(
        "django_app.governance.vendor_command_handlers.sync_or_delete_vendor_projection",
        lambda vendor: {"status": "ok"},
    )
    admin_user = User.objects.create_superuser("command-admin@example.com", "pass")
    vendor = create_pending_vendor(email="command-vendor@example.com")
    package = add_pending_package(vendor)
    media = add_portfolio_item(vendor, secure_url="https://cdn.example.com/command.jpg")

    get_command_handlers().approve_vendor(ApproveVendorCommand(admin_id=admin_user.id, vendor_id=vendor.id))

    vendor.refresh_from_db()
    package.refresh_from_db()
    media.refresh_from_db()
    assert vendor.status == VendorProfile.Status.APPROVED
    assert package.approval_status == ServicePackage.ApprovalStatus.APPROVED
    assert package.is_active is True
    assert media.visibility_status == PortfolioImage.VisibilityStatus.APPROVED
    assert AuditLog.objects.filter(action_type=AuditLog.ActionType.APPROVE_VENDOR, target_id=vendor.id).exists()
