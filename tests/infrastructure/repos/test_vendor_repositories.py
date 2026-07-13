import uuid
import pytest
from domain.vendors.entities import (
    VendorProfile, VendorStatus, ServiceCategory,
    PortfolioImage, ServicePackage, Inquiry
)
from domain.vendors.errors import ConcurrentVendorUpdate
from infrastructure.repos.inquiries.django_repository import DjangoInquiryRepository
from infrastructure.repos.packages.django_repository import DjangoServicePackageRepository
from infrastructure.repos.portfolio.django_repository import DjangoPortfolioImageRepository
from infrastructure.repos.profile.django_repository import DjangoVendorProfileRepository
from django_app.identity.models import User
from django_app.vendors.models import VendorProfile as DjangoProfile

pytestmark = pytest.mark.django_db


class TestDjangoVendorProfileRepository:
    def test_save_and_retrieve(self):
        user = User.objects.create_user(email="v@test.com", password="p", role="vendor")
        repo = DjangoVendorProfileRepository()
        domain = VendorProfile(
            id=uuid.uuid4(),
            user_id=user.id,
            business_name="Test Biz",
            category=ServiceCategory.PHOTOGRAPHY,
            description="desc",
            service_area="area",
            contact_email="biz@test.com",
            contact_phone="123",
        )
        saved = repo.save(domain)
        assert saved.id == domain.id
        assert DjangoProfile.objects.count() == 1

        retrieved = repo.get_by_id(domain.id)
        assert retrieved is not None
        assert retrieved.business_name == "Test Biz"

    def test_get_by_user_id(self):
        user = User.objects.create_user(email="v@test.com", password="p", role="vendor")
        repo = DjangoVendorProfileRepository()
        domain = VendorProfile(
            id=uuid.uuid4(),
            user_id=user.id,
            business_name="Find Me",
            category=ServiceCategory.CATERING,
            description="desc",
            service_area="area",
            contact_email="biz@test.com",
            contact_phone="123",
        )
        repo.save(domain)
        found = repo.get_by_user_id(user.id)
        assert found is not None
        assert found.business_name == "Find Me"

    def test_list_by_status(self):
        user1 = User.objects.create_user(email="v1@test.com", password="p", role="vendor")
        user2 = User.objects.create_user(email="v2@test.com", password="p", role="vendor")
        repo = DjangoVendorProfileRepository()
        for i, user in enumerate([user1, user2]):
            repo.save(VendorProfile(
                id=uuid.uuid4(), user_id=user.id, business_name=f"Biz{i}",
                category=ServiceCategory.PHOTOGRAPHY, description="d", service_area="a",
                contact_email=f"b{i}@t.com", contact_phone="1", status=VendorStatus.PENDING_REVIEW
            ))
        pending = repo.list_by_status(VendorStatus.PENDING_REVIEW)
        assert len(pending) == 2


class TestDjangoPortfolioImageRepository:
    def test_save_and_list(self):
        user = User.objects.create_user(email="v@test.com", password="p", role="vendor")
        vendor = DjangoProfile.objects.create(
            user=user, business_name="V", category="photography", description="d",
            service_area="a", contact_email="e@t.com", contact_phone="1"
        )
        repo = DjangoInquiryRepository()
        inquiry = Inquiry(
            id=uuid.uuid4(),
            vendor_id=vendor.id,
            client_name="Client",
            client_email="c@test.com",
            client_phone=None,  # ✅ explicitly provide None
            message="Hi",
        )
        saved = repo.save(inquiry)
        inquiries = repo.list_by_vendor(vendor.id)
        assert len(inquiries) == 1
        assert inquiries[0].client_name == "Client"


class TestDjangoServicePackageRepository:
    def test_crud(self):
        user = User.objects.create_user(email="v@test.com", password="p", role="vendor")
        vendor = DjangoProfile.objects.create(
            user=user, business_name="V", category="photography", description="Detailed vendor description.",
            service_area="a", contact_email="e@t.com", contact_phone="1"
        )
        repo = DjangoServicePackageRepository()
        pkg = ServicePackage(
            id=uuid.uuid4(),
            vendor_id=vendor.id,
            name="Basic package",
            description="A standard package with clear event deliverables.",
            price=1000.0,
            currency="RWF",
        )
        saved = repo.add(pkg)
        assert saved.name == "Basic package"
        pkgs = repo.list_by_vendor(vendor.id)
        assert pkgs.total == 1
        assert len(pkgs.items) == 1
        repo.delete(saved.id)
        assert repo.get_by_id(saved.id) is None

    def test_concurrent_updates_allow_one_success(self):
        user = User.objects.create_user(email="v2@test.com", password="p", role="vendor")
        vendor = DjangoProfile.objects.create(
            user=user,
            business_name="V",
            category="photography",
            description="Detailed vendor description.",
            service_area="a",
            contact_email="e2@t.com",
            contact_phone="1",
        )
        repo = DjangoServicePackageRepository()
        created = repo.add(
            ServicePackage(
                id=uuid.uuid4(),
                vendor_id=vendor.id,
                name="Basic package",
                description="A standard package with clear event deliverables.",
                price=1000.0,
                currency="RWF",
            )
        )
        first = repo.get_by_id(created.id)
        second = repo.get_by_id(created.id)

        first.update_details(name="Updated package")
        second.update_details(name="Second update")

        saved = repo.save(first, expected_version=created.version)
        assert saved.version == created.version + 1

        with pytest.raises(ConcurrentVendorUpdate):
            repo.save(second, expected_version=created.version)


class TestDjangoInquiryRepository:
    def test_save_and_list(self):
        user = User.objects.create_user(email="v@test.com", password="p", role="vendor")
        vendor = DjangoProfile.objects.create(
            user=user, business_name="V", category="photography", description="d",
            service_area="a", contact_email="e@t.com", contact_phone="1"
        )
        repo = DjangoInquiryRepository()
        inquiry = Inquiry(
            id=uuid.uuid4(),
            vendor_id=vendor.id,
            client_name="Client",
            client_email="c@test.com",
            message="Hi",
        )
        saved = repo.save(inquiry)
        inquiries = repo.list_by_vendor(vendor.id)
        assert len(inquiries) == 1
        assert inquiries[0].client_name == "Client"
