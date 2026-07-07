import uuid

import pytest
from django.core.management import call_command
from django.db import connection

from application.vendors.handlers import VendorQueryHandlers
from django_app.identity.models import User
from django_app.vendors.models import ServicePackage, VendorProfile
from domain.vendors.interfaces import PageRequest
from infrastructure.repos.django_vendor_read_repository import DjangoVendorReadRepository


pytestmark = pytest.mark.django_db


def _vendor():
    user = User.objects.create_user(email=f"vendor-{uuid.uuid4()}@example.com", password="p", role="vendor")
    return VendorProfile.objects.create(
        user=user,
        business_name="Projection Vendor",
        category=VendorProfile.Category.CATERING,
        description="Reliable catering vendor for full events.",
        service_area="Kigali",
        contact_email="projection@example.com",
        contact_phone="+250700000000",
        status=VendorProfile.Status.APPROVED,
    )


def _package(vendor, **kwargs):
    defaults = {
        "vendor": vendor,
        "name": f"Package {uuid.uuid4().hex[:8]}",
        "description": "A standard package with clear event deliverables.",
        "price": "5000.00",
        "currency": "RWF",
        "approval_status": ServicePackage.ApprovalStatus.WAITING_APPROVAL,
        "is_active": False,
    }
    defaults.update(kwargs)
    return ServicePackage.objects.create(**defaults)


def _make_waiting_package_active(package):
    if connection.vendor != "sqlite":
        pytest.skip("Legacy-invalid row insertion is implemented for sqlite test databases.")
    table = ServicePackage._meta.db_table
    with connection.cursor() as cursor:
        cursor.execute("PRAGMA ignore_check_constraints = ON")
        cursor.execute(f"UPDATE {table} SET is_active = 1 WHERE id = %s", [package.id.hex])
        cursor.execute("PRAGMA ignore_check_constraints = OFF")


def test_audit_command_exits_nonzero_for_waiting_active_legacy_row(capsys):
    vendor = _vendor()
    package = _package(vendor)
    _make_waiting_package_active(package)

    with pytest.raises(SystemExit) as exc_info:
        call_command("audit_vendor_packages")

    assert exc_info.value.code == 1
    output = capsys.readouterr().out
    assert str(package.id) in output
    assert str(vendor.id) in output
    assert "is_active" in output
    assert "description" not in output


def test_invalid_package_row_does_not_break_dashboard_metrics():
    vendor = _vendor()
    package = _package(vendor)
    _make_waiting_package_active(package)
    handlers = VendorQueryHandlers(None, None, None, None, read_repo=DjangoVendorReadRepository())

    summary = handlers.get_dashboard_summary(vendor.id)

    assert summary["total_packages"] == 1
    assert summary["pending_packages"] == 1
    assert summary["active_packages"] == 0


def test_package_listing_uses_bounded_pagination():
    vendor = _vendor()
    packages = [_package(vendor) for _ in range(3)]
    page = DjangoVendorReadRepository().list_service_packages(vendor.id, PageRequest(limit=2, offset=1))

    assert page.total == 3
    assert page.limit == 2
    assert page.offset == 1
    assert len(page.items) == 2
    assert {item.id for item in page.items}.issubset({package.id for package in packages})


def test_analytics_uses_read_projection_not_strict_package_repository():
    vendor = _vendor()
    _package(vendor)

    class StrictPackageRepo:
        def list_by_vendor(self, *args, **kwargs):
            raise AssertionError("Strict package repository should not be used for analytics.")

    handlers = VendorQueryHandlers(None, None, StrictPackageRepo(), None, read_repo=DjangoVendorReadRepository())

    analytics = handlers.get_analytics(vendor.id)

    assert analytics["total_packages"] == 1
    assert analytics["pending_packages"] == 1
