from __future__ import annotations

import uuid
from unittest.mock import Mock

import pytest
from django.db import IntegrityError

from application.vendors.errors import VendorConflict, VendorResourceNotFound
from domain.vendors.entities import PortfolioImage
from django_app.identity.models import User
from django_app.vendors.models import PortfolioImage as DjangoImage
from django_app.vendors.models import VendorProfile
from infrastructure.repos.django_portfolio_image_creation import DjangoPortfolioImageCreationPort


pytestmark = pytest.mark.django_db(transaction=True)


def _vendor(email: str = "creator@example.com") -> VendorProfile:
    user = User.objects.create_user(email=email, password="Password1!", role="vendor")
    return VendorProfile.objects.create(
        user=user,
        business_name="Creator",
        category="photography",
        description="Professional portfolio creation services.",
        service_area="Kigali",
        contact_email=email,
        contact_phone="+250700000000",
    )


def test_create_locks_vendor_calls_factory_once_and_persists_next_order():
    vendor = _vendor()
    DjangoImage.objects.create(vendor=vendor, order=0)
    factory = Mock(side_effect=lambda order: PortfolioImage(id=uuid.uuid4(), vendor_id=vendor.id, order=order))

    created = DjangoPortfolioImageCreationPort().create_at_next_order(vendor_id=vendor.id, image_factory=factory)

    factory.assert_called_once_with(1)
    assert created.order == 1
    assert DjangoImage.objects.get(id=created.id).order == 1


def test_create_rejects_missing_vendor_without_calling_factory():
    factory = Mock()

    with pytest.raises(VendorResourceNotFound):
        DjangoPortfolioImageCreationPort().create_at_next_order(vendor_id=uuid.uuid4(), image_factory=factory)

    factory.assert_not_called()


def test_create_rejects_factory_owner_mismatch_without_retry():
    vendor = _vendor()
    other = _vendor("other-creator@example.com")
    factory = Mock(return_value=PortfolioImage(id=uuid.uuid4(), vendor_id=other.id, order=0))

    with pytest.raises(VendorConflict, match="locked vendor"):
        DjangoPortfolioImageCreationPort().create_at_next_order(vendor_id=vendor.id, image_factory=factory)

    factory.assert_called_once_with(0)
    assert DjangoImage.objects.count() == 0


def test_non_order_integrity_error_is_not_retried(monkeypatch):
    vendor = _vendor()
    factory = Mock(return_value=PortfolioImage(id=uuid.uuid4(), vendor_id=vendor.id, order=0))
    adapter = DjangoPortfolioImageCreationPort()
    monkeypatch.setattr(adapter.aggregate_uow, "add_with_pending_events", Mock(side_effect=IntegrityError("other constraint")))

    with pytest.raises(IntegrityError, match="other constraint"):
        adapter.create_at_next_order(vendor_id=vendor.id, image_factory=factory)

    factory.assert_called_once_with(0)
