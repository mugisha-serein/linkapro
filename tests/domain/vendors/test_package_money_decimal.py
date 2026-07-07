from decimal import Decimal
from types import SimpleNamespace
import uuid

from domain.vendors.entities import ServicePackage
from domain.shared.utils import utc_now
from infrastructure.repos.django_service_package_repository import DjangoServicePackageRepository


def test_service_package_converts_float_input_to_decimal_from_string():
    package = ServicePackage(
        id=uuid.uuid4(),
        vendor_id=uuid.uuid4(),
        name="Standard",
        description="A clear standard event package with defined deliverables.",
        price=0.1,
    )

    assert package.price == Decimal("0.1")
    assert isinstance(package.price, Decimal)


def test_service_package_update_preserves_decimal_amount():
    package = ServicePackage(
        id=uuid.uuid4(),
        vendor_id=uuid.uuid4(),
        name="Premier",
        description="A complete premier event package with setup and support.",
        price=Decimal("50000.00"),
        approval_status="approved",
    )

    package.update_details(price="75000.25")

    assert package.price == Decimal("75000.25")
    assert package.approval_status == "waiting_approval"


def test_repository_mapper_preserves_model_decimal_without_float_conversion():
    now = utc_now()
    model = SimpleNamespace(
        id=uuid.uuid4(),
        vendor_id=uuid.uuid4(),
        name="Gold",
        description="A gold package with full delivery and coordination.",
        price=Decimal("100000.99"),
        currency="RWF",
        package_tier="gold",
        approval_status="approved",
        rejection_reason=None,
        is_active=True,
        is_deleted=False,
        deleted_at=None,
        last_approved_at=None,
        last_vendor_public_edit_at=None,
        next_vendor_edit_allowed_at=None,
        created_at=now,
        updated_at=now,
    )

    domain_package = DjangoServicePackageRepository()._to_domain(model)

    assert domain_package.price == Decimal("100000.99")
    assert isinstance(domain_package.price, Decimal)
