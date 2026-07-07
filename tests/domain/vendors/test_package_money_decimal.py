from decimal import Decimal
import uuid
from domain.shared.utils import utc_now

from domain.vendors.entities import ServicePackage


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
        last_approved_at=utc_now(),
    )

    package.update_details(price="75000.25")

    assert package.price == Decimal("75000.25")
    assert package.approval_status == "waiting_approval"
