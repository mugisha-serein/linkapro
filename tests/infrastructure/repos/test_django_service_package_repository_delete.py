from datetime import datetime, timezone as dt_timezone
from decimal import Decimal
from types import SimpleNamespace
from unittest.mock import Mock
import uuid

from infrastructure.repos.packages import django_repository as repo_module
from infrastructure.repos.packages.django_repository import DjangoServicePackageRepository


def test_delete_marks_package_inactive_deleted_and_records_deleter(monkeypatch):
    package_id = uuid.uuid4()
    vendor_id = uuid.uuid4()
    deleted_by_id = uuid.uuid4()
    deleted_at = datetime(2026, 1, 1, tzinfo=dt_timezone.utc)

    fake_model = SimpleNamespace(
        id=package_id,
        vendor_id=vendor_id,
        name="Standard package",
        description="A standard package with clear deliverables.",
        price=Decimal("5000.00"),
        currency="RWF",
        package_tier="standard",
        approval_status="approved",
        rejection_reason=None,
        is_active=True,
        is_deleted=False,
        deleted_at=None,
        deleted_by_id=None,
        last_approved_at=deleted_at,
        last_vendor_public_edit_at=None,
        next_vendor_edit_allowed_at=None,
        version=0,
        created_at=deleted_at,
        updated_at=deleted_at,
        save=Mock(),
    )

    class FakeManager:
        def get(self, id):
            assert id == package_id
            return fake_model

    class FakeDjangoPackage:
        DoesNotExist = LookupError
        all_objects = FakeManager()

    monkeypatch.setattr(repo_module, "DjangoPackage", FakeDjangoPackage)
    monkeypatch.setattr(repo_module.timezone, "now", lambda: deleted_at)

    deleted = DjangoServicePackageRepository().delete(package_id, deleted_by_id=deleted_by_id)

    assert deleted is not None
    assert deleted.id == package_id
    assert deleted.is_active is False
    assert deleted.is_deleted is True
    assert deleted.deleted_at == deleted_at
    assert fake_model.deleted_by_id == deleted_by_id
    assert fake_model.version == 1
    fake_model.save.assert_called_once_with(
        update_fields=["is_active", "is_deleted", "deleted_at", "deleted_by", "version", "updated_at"]
    )
