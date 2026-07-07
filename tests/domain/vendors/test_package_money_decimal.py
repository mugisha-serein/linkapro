from decimal import Decimal
import uuid

from domain.vendors.entities import ServicePackage
<<<<<<< HEAD
=======
from infrastructure.repos.django_service_package_repository import DjangoServicePackageRepository
>>>>>>> 028240308e063a7dfd4d77eb2f2a606995767bc4


def test_service_package_converts_float_input_to_decimal_from_string():
    package = ServicePackage(
        id=uuid.uuid4(),
        vendor_id=uuid.uuid4(),
        name="Standard",
        description="A clear standard event package with defined deliverables.",
        price=1.1,
    )

    assert package.price == Decimal("1.1")
    assert isinstance(package.price, Decimal)


def test_service_package_update_preserves_decimal_amount():
    package = ServicePackage(
        id=uuid.uuid4(),
        vendor_id=uuid.uuid4(),
        name="Premier",
        description="A complete premier event package with setup and support.",
        price=Decimal("50000.00"),
        package_tier="premier",
        approval_status="approved",
    )

    package.update_details(price="75000.25")

    assert package.price == Decimal("75000.25")
    assert package.approval_status == "waiting_approval"
<<<<<<< HEAD
=======


def test_repository_mapper_preserves_model_decimal_without_float_conversion():
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
        created_at=None,
        updated_at=None,
    )

    domain_package = DjangoServicePackageRepository()._to_domain(model)

    assert domain_package.price == Decimal("100000.99")
    assert isinstance(domain_package.price, Decimal)
>>>>>>> 028240308e063a7dfd4d77eb2f2a606995767bc4
