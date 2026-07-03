from decimal import Decimal
import uuid

import pytest
from sqlalchemy import delete
from sqlalchemy.ext.asyncio import AsyncSession

from application.marketplace.search_service import MarketplaceSearchCriteria, MarketplaceSearchService
from fastapi_app.marketplace.models import VendorListingModel

pytestmark = pytest.mark.asyncio


async def test_marketplace_search_filters_by_projected_starting_price(session: AsyncSession):
    await session.execute(delete(VendorListingModel))
    await session.commit()
    session.add_all(
        [
            VendorListingModel(
                vendor_id=uuid.uuid4(),
                business_name="Budget Photographer",
                category="photography",
                description="Affordable approved listing",
                service_area="Kigali",
                approval_status="approved",
                is_verified=True,
                starting_price=Decimal("10000.00"),
                min_package_price=Decimal("10000.00"),
                max_package_price=Decimal("25000.00"),
                currency="RWF",
            ),
            VendorListingModel(
                vendor_id=uuid.uuid4(),
                business_name="Premium Photographer",
                category="photography",
                description="Premium approved listing",
                service_area="Kigali",
                approval_status="approved",
                is_verified=True,
                starting_price=Decimal("80000.00"),
                min_package_price=Decimal("80000.00"),
                max_package_price=Decimal("150000.00"),
                currency="RWF",
            ),
            VendorListingModel(
                vendor_id=uuid.uuid4(),
                business_name="Hidden Cheap Photographer",
                category="photography",
                description="Rejected listing must remain hidden",
                service_area="Kigali",
                approval_status="rejected",
                starting_price=Decimal("5000.00"),
                min_package_price=Decimal("5000.00"),
                max_package_price=Decimal("5000.00"),
                currency="RWF",
            ),
        ]
    )
    await session.commit()

    service = MarketplaceSearchService(session=session, cache=None)
    result = await service.search(
        MarketplaceSearchCriteria(category="photography", min_price=Decimal("9000.00"), max_price=Decimal("30000.00")),
        client_id="test-client",
    )

    assert result.total == 1
    assert result.items[0].business_name == "Budget Photographer"
    assert result.items[0].starting_price == Decimal("10000.00")
    assert result.items[0].min_package_price == Decimal("10000.00")
    assert result.items[0].max_package_price == Decimal("25000.00")
    assert result.items[0].currency == "RWF"


async def test_marketplace_search_excludes_unpriced_listings_when_price_filter_is_used(session: AsyncSession):
    await session.execute(delete(VendorListingModel))
    await session.commit()
    session.add_all(
        [
            VendorListingModel(
                vendor_id=uuid.uuid4(),
                business_name="Unpriced Vendor",
                category="decor",
                description="Approved but has no approved active package yet.",
                service_area="Kigali",
                approval_status="approved",
                is_verified=True,
            ),
            VendorListingModel(
                vendor_id=uuid.uuid4(),
                business_name="Priced Vendor",
                category="decor",
                description="Approved and priced listing.",
                service_area="Kigali",
                approval_status="approved",
                is_verified=True,
                starting_price=Decimal("20000.00"),
                min_package_price=Decimal("20000.00"),
                max_package_price=Decimal("35000.00"),
                currency="RWF",
            ),
        ]
    )
    await session.commit()

    service = MarketplaceSearchService(session=session, cache=None)
    result = await service.search(
        MarketplaceSearchCriteria(category="decor", max_price=Decimal("25000.00")),
        client_id="test-client",
    )

    assert result.total == 1
    assert result.items[0].business_name == "Priced Vendor"
