from decimal import Decimal

import pytest

from domain.vendors.shared.pagination import PageRequest
from infrastructure.repos.packages.django_repository import DjangoServicePackageRepository
from tests.factories import create_service_package, create_vendor_profile

pytestmark = pytest.mark.django_db


def test_service_package_repository_search_filters_text_tier_and_vendor():
    vendor = create_vendor_profile(description="Professional event coverage across Kigali and beyond.")
    other_vendor = create_vendor_profile(description="Professional event coverage across Kigali and beyond.")
    matching = create_service_package(
        vendor=vendor,
        name="Wedding Gold Package",
        description=(
            "Full reception planning, decor, vendor coordination, premium logistics, "
            "and complete event support."
        ),
        price=Decimal("2500000.00"),
        package_tier="gold",
    )
    create_service_package(
        vendor=vendor,
        name="Wedding Standard Package",
        description="Simple reception support.",
        price=Decimal("800000.00"),
        package_tier="standard",
    )
    create_service_package(
        vendor=vendor,
        name="Corporate Gold Package",
        description="Conference planning.",
        price=Decimal("1800000.00"),
        package_tier="gold",
    )
    create_service_package(
        vendor=other_vendor,
        name="Wedding Gold Package",
        description=(
            "Full reception planning, decor, vendor coordination, premium logistics, "
            "and complete event support."
        ),
        price=Decimal("2500000.00"),
        package_tier="gold",
    )

    page = DjangoServicePackageRepository().search(
        vendor.id,
        "wedding",
        "gold",
        PageRequest(limit=10),
    )

    assert page.total == 1
    assert [item.id for item in page.items] == [matching.id]
