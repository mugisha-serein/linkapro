import uuid

import pytest
from django.utils import timezone

from django_app.governance.marketplace_outbox import enqueue_vendor_projection
from django_app.governance.models import MarketplaceProjectionOutbox
from django_app.identity.models import User
from django_app.vendors.models import ServicePackage, VendorProfile

pytestmark = pytest.mark.django_db


def create_approved_vendor():
    user = User.objects.create_user(email=f"vendor-{uuid.uuid4()}@example.com", password="pass", role="vendor")
    return VendorProfile.objects.create(
        user=user,
        business_name="Projection Pricing Vendor",
        category=VendorProfile.Category.PHOTOGRAPHY,
        description="A complete public vendor profile.",
        service_area="Kigali",
        contact_email="vendor@example.com",
        contact_phone="+250788000000",
        status=VendorProfile.Status.APPROVED,
        approved_at=timezone.now(),
    )


def test_projection_pricing_uses_only_approved_active_packages(monkeypatch):
    monkeypatch.setattr(
        "tasks.marketplace_sync.deliver_marketplace_projection_outbox_event_task.delay",
        lambda event_id: None,
    )
    vendor = create_approved_vendor()
    ServicePackage.objects.create(
        vendor=vendor,
        name="Rejected Package",
        description="Rejected package should never affect public pricing.",
        price="5000.00",
        currency="RWF",
        approval_status=ServicePackage.ApprovalStatus.REJECTED,
        is_active=False,
    )
    ServicePackage.objects.create(
        vendor=vendor,
        name="Inactive Approved Package",
        description="Inactive package should never affect public pricing.",
        price="7500.00",
        currency="RWF",
        approval_status=ServicePackage.ApprovalStatus.APPROVED,
        is_active=False,
    )
    ServicePackage.objects.create(
        vendor=vendor,
        name="Standard Package",
        description="Approved active package should affect pricing.",
        price="10000.00",
        currency="RWF",
        approval_status=ServicePackage.ApprovalStatus.APPROVED,
        is_active=True,
    )
    ServicePackage.objects.create(
        vendor=vendor,
        name="Gold Package",
        description="Approved active package should affect pricing.",
        price="45000.00",
        currency="RWF",
        approval_status=ServicePackage.ApprovalStatus.APPROVED,
        is_active=True,
    )

    event = enqueue_vendor_projection(vendor, reason="pricing_projection")

    assert event.event_type == MarketplaceProjectionOutbox.EventType.UPSERT_VENDOR
    assert event.payload["starting_price"] == "10000.00"
    assert event.payload["min_package_price"] == "10000.00"
    assert event.payload["max_package_price"] == "45000.00"
    assert event.payload["currency"] == "RWF"


def test_projection_pricing_is_empty_when_vendor_has_no_approved_active_packages(monkeypatch):
    monkeypatch.setattr(
        "tasks.marketplace_sync.deliver_marketplace_projection_outbox_event_task.delay",
        lambda event_id: None,
    )
    vendor = create_approved_vendor()
    ServicePackage.objects.create(
        vendor=vendor,
        name="Waiting Package",
        description="Waiting package should not be public yet.",
        price="9000.00",
        currency="RWF",
        approval_status=ServicePackage.ApprovalStatus.WAITING_APPROVAL,
        is_active=True,
    )

    event = enqueue_vendor_projection(vendor, reason="pricing_projection")

    assert event.payload["starting_price"] is None
    assert event.payload["min_package_price"] is None
    assert event.payload["max_package_price"] is None
    assert event.payload["currency"] is None
