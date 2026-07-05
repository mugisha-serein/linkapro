import uuid
from datetime import timedelta

import pytest
from django.utils import timezone

from django_app.governance.marketplace_outbox import (
    deliver_marketplace_projection_outbox_event,
    enqueue_vendor_delete_projection,
    enqueue_vendor_projection,
)
from django_app.governance.models import MarketplaceProjectionOutbox
from django_app.identity.models import User
from django_app.vendors.models import VendorProfile
from tasks.marketplace_sync import retry_due_marketplace_projection_outbox_events_task

pytestmark = pytest.mark.django_db


def create_vendor(*, status=VendorProfile.Status.APPROVED):
    user = User.objects.create_user(email=f"vendor-{uuid.uuid4()}@example.com", password="pass", role="vendor")
    return VendorProfile.objects.create(
        user=user,
        business_name="Outbox Vendor",
        category=VendorProfile.Category.PHOTOGRAPHY,
        description="A complete public vendor profile.",
        service_area="Kigali",
        contact_email="vendor@example.com",
        contact_phone="+250788000000",
        status=status,
        approved_at=timezone.now() if status == VendorProfile.Status.APPROVED else None,
    )


def test_enqueue_approved_vendor_creates_upsert_outbox_event(monkeypatch, django_capture_on_commit_callbacks):
    scheduled = []
    monkeypatch.setattr(
        "tasks.marketplace_sync.deliver_marketplace_projection_outbox_event_task.delay",
        lambda event_id: scheduled.append(event_id),
    )
    vendor = create_vendor()

    with django_capture_on_commit_callbacks(execute=True):
        event = enqueue_vendor_projection(vendor, reason="vendor_approved")

    assert event.event_type == MarketplaceProjectionOutbox.EventType.UPSERT_VENDOR
    assert event.status == MarketplaceProjectionOutbox.Status.PENDING
    assert event.vendor_id == vendor.id
    assert event.payload["vendor_id"] == str(vendor.id)
    assert event.payload["business_name"] == vendor.business_name
    assert scheduled == [str(event.id)]


def test_enqueue_non_listable_vendor_creates_delete_outbox_event(monkeypatch, django_capture_on_commit_callbacks):
    scheduled = []
    monkeypatch.setattr(
        "tasks.marketplace_sync.deliver_marketplace_projection_outbox_event_task.delay",
        lambda event_id: scheduled.append(event_id),
    )
    vendor = create_vendor(status=VendorProfile.Status.SUSPENDED)

    with django_capture_on_commit_callbacks(execute=True):
        event = enqueue_vendor_projection(vendor, reason="vendor_suspended")

    assert event.event_type == MarketplaceProjectionOutbox.EventType.DELETE_VENDOR
    assert event.payload["reason"] == "vendor_suspended"
    assert scheduled == [str(event.id)]


def test_enqueue_delete_projection_does_not_require_existing_vendor(monkeypatch, django_capture_on_commit_callbacks):
    scheduled = []
    vendor_id = uuid.uuid4()
    monkeypatch.setattr(
        "tasks.marketplace_sync.deliver_marketplace_projection_outbox_event_task.delay",
        lambda event_id: scheduled.append(event_id),
    )

    with django_capture_on_commit_callbacks(execute=True):
        event = enqueue_vendor_delete_projection(vendor_id, reason="vendor_deleted")

    assert event.event_type == MarketplaceProjectionOutbox.EventType.DELETE_VENDOR
    assert event.vendor_id == vendor_id
    assert event.payload["vendor_id"] == str(vendor_id)
    assert scheduled == [str(event.id)]


def test_enqueue_schedule_failure_leaves_event_pending(monkeypatch, django_capture_on_commit_callbacks):
    def fail_schedule(event_id):
        raise RuntimeError("broker unavailable")

    monkeypatch.setattr("tasks.marketplace_sync.deliver_marketplace_projection_outbox_event_task.delay", fail_schedule)
    vendor = create_vendor()

    with django_capture_on_commit_callbacks(execute=True):
        event = enqueue_vendor_projection(vendor, reason="vendor_approved")

    event.refresh_from_db()
    assert event.status == MarketplaceProjectionOutbox.Status.PENDING
    assert event.attempts == 0


def test_deliver_upsert_marks_event_delivered(monkeypatch):
    vendor = create_vendor()
    event = MarketplaceProjectionOutbox.objects.create(
        event_type=MarketplaceProjectionOutbox.EventType.UPSERT_VENDOR,
        vendor_id=vendor.id,
        payload={
            "vendor_id": str(vendor.id),
            "business_name": vendor.business_name,
            "category": vendor.category,
            "description": vendor.description,
            "service_area": vendor.service_area,
            "approval_status": VendorProfile.Status.APPROVED,
        },
    )
    calls = []
    monkeypatch.setattr(
        "django_app.governance.marketplace_outbox.sync_vendor_payload_to_marketplace",
        lambda **payload: calls.append(payload) or {"status": "ok"},
    )

    delivered = deliver_marketplace_projection_outbox_event(event.id)

    event.refresh_from_db()
    assert delivered is True
    assert event.status == MarketplaceProjectionOutbox.Status.DELIVERED
    assert event.attempts == 1
    assert calls[0]["vendor_id"] == str(vendor.id)


def test_failed_delivery_returns_event_to_pending(monkeypatch):
    vendor = create_vendor()
    event = MarketplaceProjectionOutbox.objects.create(
        event_type=MarketplaceProjectionOutbox.EventType.DELETE_VENDOR,
        vendor_id=vendor.id,
        payload={"vendor_id": str(vendor.id)},
    )

    def fail(*args, **kwargs):
        raise RuntimeError("fastapi unavailable")

    monkeypatch.setattr("django_app.governance.marketplace_outbox.delete_vendor_from_marketplace", fail)

    with pytest.raises(RuntimeError):
        deliver_marketplace_projection_outbox_event(event.id)

    event.refresh_from_db()
    assert event.status == MarketplaceProjectionOutbox.Status.PENDING
    assert event.attempts == 1
    assert "fastapi unavailable" in event.last_error
    assert event.next_attempt_at > timezone.now()


def test_failed_delivery_at_max_attempts_marks_failed(monkeypatch):
    vendor = create_vendor()
    event = MarketplaceProjectionOutbox.objects.create(
        event_type=MarketplaceProjectionOutbox.EventType.DELETE_VENDOR,
        vendor_id=vendor.id,
        payload={"vendor_id": str(vendor.id)},
        attempts=4,
        next_attempt_at=timezone.now(),
    )

    def fail(*args, **kwargs):
        raise RuntimeError("fastapi unavailable")

    monkeypatch.setattr("django_app.governance.marketplace_outbox.delete_vendor_from_marketplace", fail)

    with pytest.raises(RuntimeError):
        deliver_marketplace_projection_outbox_event(event.id)

    event.refresh_from_db()
    assert event.status == MarketplaceProjectionOutbox.Status.FAILED
    assert event.attempts == 5


def test_retry_task_picks_pending_due_event(monkeypatch):
    vendor = create_vendor()
    event = MarketplaceProjectionOutbox.objects.create(
        event_type=MarketplaceProjectionOutbox.EventType.DELETE_VENDOR,
        vendor_id=vendor.id,
        payload={"vendor_id": str(vendor.id)},
        next_attempt_at=timezone.now(),
    )
    delivered = []
    monkeypatch.setattr(
        "django_app.governance.marketplace_outbox.deliver_marketplace_projection_outbox_event",
        lambda event_id: delivered.append(event_id) or True,
    )

    result = retry_due_marketplace_projection_outbox_events_task.run(batch_size=10)

    assert result == {"processed": 1, "delivered": 1, "failed": 0, "errors": 0}
    assert delivered == [event.id]


def test_retry_task_skips_delivered_failed_and_not_due_events(monkeypatch):
    vendor = create_vendor()
    due_event = MarketplaceProjectionOutbox.objects.create(
        event_type=MarketplaceProjectionOutbox.EventType.DELETE_VENDOR,
        vendor_id=vendor.id,
        payload={"vendor_id": str(vendor.id)},
        next_attempt_at=timezone.now(),
    )
    MarketplaceProjectionOutbox.objects.create(
        event_type=MarketplaceProjectionOutbox.EventType.DELETE_VENDOR,
        vendor_id=vendor.id,
        payload={"vendor_id": str(vendor.id)},
        status=MarketplaceProjectionOutbox.Status.DELIVERED,
        next_attempt_at=timezone.now(),
    )
    MarketplaceProjectionOutbox.objects.create(
        event_type=MarketplaceProjectionOutbox.EventType.DELETE_VENDOR,
        vendor_id=vendor.id,
        payload={"vendor_id": str(vendor.id)},
        status=MarketplaceProjectionOutbox.Status.FAILED,
        next_attempt_at=timezone.now(),
    )
    MarketplaceProjectionOutbox.objects.create(
        event_type=MarketplaceProjectionOutbox.EventType.DELETE_VENDOR,
        vendor_id=vendor.id,
        payload={"vendor_id": str(vendor.id)},
        next_attempt_at=timezone.now() + timedelta(hours=1),
    )
    delivered = []
    monkeypatch.setattr(
        "django_app.governance.marketplace_outbox.deliver_marketplace_projection_outbox_event",
        lambda event_id: delivered.append(event_id) or True,
    )

    result = retry_due_marketplace_projection_outbox_events_task.run(batch_size=10)

    assert result["processed"] == 1
    assert delivered == [due_event.id]
