from types import SimpleNamespace
from unittest.mock import Mock
import uuid

import pytest

from domain.vendors.entities import (
    Inquiry,
    PortfolioImage,
    ServiceCategory,
    ServicePackage,
    VendorProfile,
)
from infrastructure.repos import django_inquiry_repository as inquiry_repo_module
from infrastructure.repos import django_portfolio_image_repository as image_repo_module
from infrastructure.repos import django_service_package_repository as package_repo_module
from infrastructure.repos import django_vendor_profile_repository as profile_repo_module
from infrastructure.repos.django_inquiry_repository import DjangoInquiryRepository
from infrastructure.repos.django_portfolio_image_repository import DjangoPortfolioImageRepository
from infrastructure.repos.django_service_package_repository import DjangoServicePackageRepository
from infrastructure.repos.django_vendor_profile_repository import DjangoVendorProfileRepository
from infrastructure.repos.exceptions import RepositoryNotFoundError


class _MissingManager:
    def __init__(self, exc):
        self.exc = exc

    def get(self, **kwargs):
        raise self.exc


class _ExistingObjectManager:
    def __init__(self, obj):
        self.obj = obj

    def get(self, **kwargs):
        return self.obj


class _MissingDjangoUser:
    class DoesNotExist(Exception):
        pass

    objects = _MissingManager(DoesNotExist())


class _MissingDjangoVendor:
    class DoesNotExist(Exception):
        pass

    objects = _MissingManager(DoesNotExist())


def _existing_model():
    return SimpleNamespace(save=Mock())


def test_vendor_profile_repository_translates_missing_user(monkeypatch):
    model = _existing_model()
    monkeypatch.setattr(profile_repo_module, "User", _MissingDjangoUser)
    monkeypatch.setattr(profile_repo_module.DjangoProfile, "objects", _ExistingObjectManager(model))

    profile = VendorProfile(
        id=uuid.uuid4(),
        user_id=uuid.uuid4(),
        business_name="Vendor",
        category=ServiceCategory.CATERING,
        description="Reliable catering vendor.",
        service_area="Kigali",
        contact_email="vendor@example.com",
        contact_phone="+250700000000",
    )

    with pytest.raises(RepositoryNotFoundError, match="User not found"):
        DjangoVendorProfileRepository().save(profile)

    model.save.assert_not_called()


def test_service_package_repository_translates_missing_vendor(monkeypatch):
    model = _existing_model()
    monkeypatch.setattr(package_repo_module, "DjangoVendor", _MissingDjangoVendor)
    monkeypatch.setattr(package_repo_module.DjangoPackage, "all_objects", _ExistingObjectManager(model))

    package = ServicePackage(
        id=uuid.uuid4(),
        vendor_id=uuid.uuid4(),
        name="Standard package",
        description="A standard package with clear event deliverables.",
        price="5000.00",
    )

    with pytest.raises(RepositoryNotFoundError, match="Vendor not found"):
        DjangoServicePackageRepository().save(package)

    model.save.assert_not_called()


def test_portfolio_image_repository_translates_missing_vendor(monkeypatch):
    model = _existing_model()
    monkeypatch.setattr(image_repo_module, "DjangoVendor", _MissingDjangoVendor)
    monkeypatch.setattr(image_repo_module.DjangoImage, "objects", _ExistingObjectManager(model))

    image = PortfolioImage(
        id=uuid.uuid4(),
        vendor_id=uuid.uuid4(),
        public_id="portfolio/image",
        secure_url="https://example.com/image.jpg",
    )

    with pytest.raises(RepositoryNotFoundError, match="Vendor not found"):
        DjangoPortfolioImageRepository().save(image)

    model.save.assert_not_called()


def test_inquiry_repository_translates_missing_vendor(monkeypatch):
    model = _existing_model()
    monkeypatch.setattr(inquiry_repo_module, "DjangoVendor", _MissingDjangoVendor)
    monkeypatch.setattr(inquiry_repo_module.DjangoInquiry, "objects", _ExistingObjectManager(model))

    inquiry = Inquiry(
        id=uuid.uuid4(),
        vendor_id=uuid.uuid4(),
        client_name="Planner",
        client_email="planner@example.com",
        client_phone=None,
        message="We need support for an event.",
        event_date=None,
    )

    with pytest.raises(RepositoryNotFoundError, match="Vendor not found"):
        DjangoInquiryRepository().save(inquiry)

    model.save.assert_not_called()
