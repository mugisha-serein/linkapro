import uuid
from io import StringIO

import pytest
from django.core.management import call_command
from django.utils import timezone

from django_app.governance.marketplace_reconciliation import reconcile_marketplace_projection
from django_app.identity.models import User
from django_app.vendors.models import VendorProfile

pytestmark = pytest.mark.django_db


def create_vendor(*, status=VendorProfile.Status.APPROVED, description="A complete public vendor profile."):
    user = User.objects.create_user(email=f"vendor-{uuid.uuid4()}@example.com", password="pass", role="vendor")
    return VendorProfile.objects.create(
        user=user,
        business_name="Reconciliation Vendor",
        category=VendorProfile.Category.PHOTOGRAPHY,
        description=description,
        service_area="Kigali",
        contact_email="vendor@example.com",
        contact_phone="+250788000000",
        status=status,
        approved_at=timezone.now() if status == VendorProfile.Status.APPROVED else None,
    )


def test_reconciliation_enqueues_approved_complete_and_deletes_stale_fastapi_rows(monkeypatch):
    approved = create_vendor()
    rejected = create_vendor(status=VendorProfile.Status.REJECTED)
    incomplete = create_vendor(description="Too short")
    missing_vendor_id = str(uuid.uuid4())
    enqueued = []
    deleted = []

    monkeypatch.setattr(
        "django_app.governance.marketplace_reconciliation.list_marketplace_projection_vendor_ids",
        lambda: {str(approved.id), str(rejected.id), str(incomplete.id), missing_vendor_id},
    )
    monkeypatch.setattr(
        "django_app.governance.marketplace_reconciliation.enqueue_vendor_projection",
        lambda vendor, reason=None: enqueued.append((str(vendor.id), reason)),
    )
    monkeypatch.setattr(
        "django_app.governance.marketplace_reconciliation.delete_vendor_from_marketplace",
        lambda vendor_id: deleted.append(str(vendor_id)) or {"status": "ok", "deleted": True},
    )

    result = reconcile_marketplace_projection()

    assert result.django_approved_complete_count == 1
    assert result.fastapi_projection_count == 4
    assert result.stale_projection_count == 3
    assert result.upsert_enqueued_count == 1
    assert result.deleted_stale_count == 3
    assert enqueued == [(str(approved.id), "marketplace_reconciliation")]
    assert deleted == sorted([str(rejected.id), str(incomplete.id), missing_vendor_id])


def test_reconciliation_dry_run_does_not_delete_or_enqueue(monkeypatch):
    approved = create_vendor()
    stale_vendor_id = str(uuid.uuid4())
    enqueued = []
    deleted = []
    monkeypatch.setattr(
        "django_app.governance.marketplace_reconciliation.list_marketplace_projection_vendor_ids",
        lambda: {str(approved.id), stale_vendor_id},
    )
    monkeypatch.setattr(
        "django_app.governance.marketplace_reconciliation.enqueue_vendor_projection",
        lambda vendor, reason=None: enqueued.append(str(vendor.id)),
    )
    monkeypatch.setattr(
        "django_app.governance.marketplace_reconciliation.delete_vendor_from_marketplace",
        lambda vendor_id: deleted.append(str(vendor_id)) or {"status": "ok", "deleted": True},
    )

    result = reconcile_marketplace_projection(dry_run=True)

    assert result.dry_run is True
    assert result.django_approved_complete_count == 1
    assert result.fastapi_projection_count == 2
    assert result.stale_projection_count == 1
    assert result.upsert_enqueued_count == 0
    assert result.deleted_stale_count == 0
    assert enqueued == []
    assert deleted == []


def test_reconciliation_deletes_all_fastapi_rows_when_django_has_no_approved_vendors(monkeypatch):
    create_vendor(status=VendorProfile.Status.PENDING_REVIEW)
    stale_ids = {str(uuid.uuid4()) for _ in range(4)}
    deleted = []
    monkeypatch.setattr(
        "django_app.governance.marketplace_reconciliation.list_marketplace_projection_vendor_ids",
        lambda: stale_ids,
    )
    monkeypatch.setattr(
        "django_app.governance.marketplace_reconciliation.delete_vendor_from_marketplace",
        lambda vendor_id: deleted.append(str(vendor_id)) or {"status": "ok", "deleted": True},
    )

    result = reconcile_marketplace_projection()

    assert result.django_approved_complete_count == 0
    assert result.fastapi_projection_count == 4
    assert result.stale_projection_count == 4
    assert result.deleted_stale_count == 4
    assert sorted(deleted) == sorted(stale_ids)


def test_reconciliation_management_command_prints_counts(monkeypatch):
    monkeypatch.setattr(
        "django_app.governance.management.commands.reconcile_marketplace_projection.reconcile_marketplace_projection",
        lambda dry_run=False: type(
            "Result",
            (),
            {
                "django_approved_complete_count": 0,
                "fastapi_projection_count": 4,
                "stale_projection_count": 4,
                "deleted_stale_count": 4,
                "upsert_enqueued_count": 0,
                "dry_run": dry_run,
            },
        )(),
    )
    out = StringIO()

    call_command("reconcile_marketplace_projection", "--dry-run", stdout=out)

    output = out.getvalue()
    assert "Django approved complete vendors: 0" in output
    assert "FastAPI marketplace listings: 4" in output
    assert "Stale FastAPI listings to delete: 4" in output
    assert "Dry run: no marketplace projection changes applied." in output
    assert "Marketplace projection reconciliation completed." in output
