import uuid
from unittest.mock import Mock

import pytest

from domain.vendors.entities import ServiceCategory, VendorProfile, VendorStatus
from django_app.identity.models import User
from infrastructure.repos.django_vendor_profile_repository import DjangoVendorProfileRepository


pytestmark = pytest.mark.django_db(transaction=True)


def _create_vendor_user() -> User:
    return User.objects.create(
        email=f"vendor-{uuid.uuid4().hex}@example.com",
        first_name="Vendor",
        last_name="User",
        role="vendor",
        is_active=True,
        is_verified=True,
    )


def _profile_for(user: User, *, status: VendorStatus = VendorStatus.APPROVED) -> VendorProfile:
    return VendorProfile(
        id=uuid.uuid4(),
        user_id=user.id,
        business_name="Projection Ready Vendor",
        category=ServiceCategory.PHOTOGRAPHY,
        description="Professional photography services for weddings and events.",
        service_area="Kigali, Rwanda",
        contact_email="vendor@example.com",
        contact_phone="+250700000000",
        status=status,
    )


def test_save_schedules_marketplace_projection_sync(monkeypatch):
    repo = DjangoVendorProfileRepository()
    sync_mock = Mock()
    monkeypatch.setattr(repo, "_sync_marketplace_projection", sync_mock)

    saved = repo.save(_profile_for(_create_vendor_user(), status=VendorStatus.APPROVED))

    assert saved.status == VendorStatus.APPROVED
    sync_mock.assert_called_once_with(saved.id)


def test_delete_removes_marketplace_projection(monkeypatch):
    delete_mock = Mock(return_value={"status": "deleted"})
    monkeypatch.setattr(
        "infrastructure.repos.django_vendor_profile_repository.delete_vendor_from_marketplace",
        delete_mock,
    )
    repo = DjangoVendorProfileRepository()
    saved = repo.save(_profile_for(_create_vendor_user(), status=VendorStatus.APPROVED))

    repo.delete(saved.id)

    delete_mock.assert_called_once_with(saved.id)
