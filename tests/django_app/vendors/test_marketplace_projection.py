from io import StringIO

import pytest
from django.core.management import call_command
from django.core.management.base import CommandError

from django_app.identity.models import User
from django_app.vendors.models import VendorProfile

pytestmark = pytest.mark.django_db


def _create_vendor(email: str, status: str, business_name: str) -> VendorProfile:
    user = User.objects.create_user(email=email, password="p", role="vendor")
    return VendorProfile.objects.create(
        user=user,
        business_name=business_name,
        category=VendorProfile.Category.PHOTOGRAPHY,
        description="A complete vendor description.",
        service_area="Kigali, Rwanda",
        contact_email=email,
        contact_phone="123",
        status=status,
    )


def test_sync_marketplace_listings_backfills_only_approved_vendors(monkeypatch):
    approved = _create_vendor("approved@example.com", VendorProfile.Status.APPROVED, "Approved")
    _create_vendor("rejected@example.com", VendorProfile.Status.REJECTED, "Rejected")
    calls = []

    monkeypatch.setattr(
        "django_app.vendors.management.commands.sync_marketplace_listings.sync_vendor_to_marketplace",
        lambda vendor: calls.append(vendor.id) or {"status": "ok"},
    )

    stdout = StringIO()
    call_command("sync_marketplace_listings", stdout=stdout)

    assert calls == [approved.id]
    assert "synced=1 failed=0 skipped=0" in stdout.getvalue()


def test_sync_marketplace_listings_counts_skipped_vendors(monkeypatch):
    _create_vendor("approved@example.com", VendorProfile.Status.APPROVED, "Approved")

    monkeypatch.setattr(
        "django_app.vendors.management.commands.sync_marketplace_listings.sync_vendor_to_marketplace",
        lambda vendor: {"status": "skipped"},
    )

    stdout = StringIO()
    call_command("sync_marketplace_listings", stdout=stdout)

    assert "synced=0 failed=0 skipped=1" in stdout.getvalue()


def test_sync_marketplace_listings_continues_then_exits_non_zero_on_failures(monkeypatch):
    first = _create_vendor("first@example.com", VendorProfile.Status.APPROVED, "First")
    second = _create_vendor("second@example.com", VendorProfile.Status.APPROVED, "Second")
    calls = []

    def fake_sync(vendor):
        calls.append(vendor.id)
        if vendor.id == first.id:
            raise RuntimeError("boom")
        return {"status": "ok"}

    monkeypatch.setattr(
        "django_app.vendors.management.commands.sync_marketplace_listings.sync_vendor_to_marketplace",
        fake_sync,
    )

    stdout = StringIO()
    stderr = StringIO()
    with pytest.raises(CommandError):
        call_command("sync_marketplace_listings", stdout=stdout, stderr=stderr)

    assert set(calls) == {first.id, second.id}
    assert len(calls) == 2
    assert "synced=1 failed=1 skipped=0" in stdout.getvalue()
    assert "Failed to sync vendor" in stderr.getvalue()
