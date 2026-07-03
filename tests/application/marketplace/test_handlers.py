import uuid
import pytest
from unittest.mock import AsyncMock, Mock
from datetime import datetime

from application.marketplace.commands import (
    UpdateVendorListingCommand,
    PostReviewCommand,
)
from application.marketplace.queries import GetVendorListingQuery, SearchVendorsQuery
from application.marketplace.handlers import (
    MarketplaceCommandHandlers,
    MarketplaceQueryHandlers,
)
from domain.marketplace.entities import VendorListing, Review


@pytest.fixture
def mock_listing_repo():
    repo = AsyncMock()
    return repo


@pytest.fixture
def mock_review_repo():
    repo = AsyncMock()
    return repo


@pytest.fixture
def mock_event_dispatcher():
    dispatcher = Mock()
    return dispatcher


@pytest.fixture
def command_handlers(mock_listing_repo, mock_review_repo, mock_event_dispatcher):
    return MarketplaceCommandHandlers(
        listing_repo=mock_listing_repo,
        review_repo=mock_review_repo,
        event_dispatcher=mock_event_dispatcher,
    )


@pytest.fixture
def query_handlers(mock_listing_repo, mock_review_repo):
    return MarketplaceQueryHandlers(
        listing_repo=mock_listing_repo,
        review_repo=mock_review_repo,
    )


class TestMarketplaceCommandHandlers:
    @pytest.mark.asyncio
    async def test_update_vendor_listing_new(self, command_handlers, mock_listing_repo):
        mock_listing_repo.get_by_vendor_id.return_value = None
        mock_listing_repo.save.side_effect = lambda x: x

        vendor_id = uuid.uuid4()
        cmd = UpdateVendorListingCommand(
            vendor_id=vendor_id,
            business_name="New Biz",
            category="photography",
            description="desc",
            service_area="Kigali",
            cover_image_url=None, 
        )
        result = await command_handlers.update_vendor_listing(cmd)

        assert result.business_name == "New Biz"
        mock_listing_repo.save.assert_called_once()

    @pytest.mark.asyncio
    async def test_update_vendor_listing_existing(self, command_handlers, mock_listing_repo):
        existing = VendorListing(
            id=uuid.uuid4(),
            vendor_id=uuid.uuid4(),
            business_name="Old",
            category="catering",
            description="old desc",
            service_area="area",
            cover_image_url=None, 
        )
        mock_listing_repo.get_by_vendor_id.return_value = existing
        mock_listing_repo.save.side_effect = lambda x: x

        cmd = UpdateVendorListingCommand(
            vendor_id=existing.vendor_id,
            business_name="New Name",
        )
        result = await command_handlers.update_vendor_listing(cmd)

        assert result.business_name == "New Name"
        assert result.category == "catering"  # unchanged

    @pytest.mark.asyncio
    async def test_post_review(self, command_handlers, mock_review_repo):
        mock_review_repo.save.side_effect = lambda r: r

        cmd = PostReviewCommand(
            vendor_id=uuid.uuid4(),
            author_user_id=uuid.uuid4(),
            rating=5,
            comment="Excellent!",
        )
        result = await command_handlers.post_review(cmd)

        assert result.rating == 5
        mock_review_repo.save.assert_called_once()


class TestMarketplaceQueryHandlers:
    @pytest.mark.asyncio
    async def test_search_vendors(self, query_handlers, mock_listing_repo):
        query = SearchVendorsQuery(query="Biz", page=1, page_size=10)

        with pytest.raises(RuntimeError, match="Legacy marketplace search handler is disabled"):
            await query_handlers.search_vendors(query)

    @pytest.mark.asyncio
    async def test_get_vendor_listing_uses_public_vendor_id(self, query_handlers, mock_listing_repo):
        listing_id = uuid.uuid4()
        vendor_id = uuid.uuid4()
        mock_listing_repo.get_by_vendor_id.return_value = VendorListing(
            id=listing_id,
            vendor_id=vendor_id,
            business_name="Biz1",
            category="photography",
            description="...",
            service_area="Kigali",
            cover_image_url=None,
        )

        result = await query_handlers.get_vendor_listing(GetVendorListingQuery(vendor_id=str(vendor_id)))

        assert result.id == str(vendor_id)
        assert result.id != str(listing_id)
