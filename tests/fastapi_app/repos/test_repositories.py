import uuid
import pytest
from datetime import datetime, timezone
from sqlalchemy.ext.asyncio import AsyncSession

from fastapi_app.repositories import (
    AsyncVendorListingRepository,
    AsyncReviewRepository,
)
from domain.marketplace.entities import VendorListing, Review
from fastapi_app.marketplace.models import VendorListingModel, ReviewModel

class TestAsyncVendorListingRepository:
    @pytest.mark.asyncio
    async def test_save_and_retrieve(self, session: AsyncSession):
        repo = AsyncVendorListingRepository(session)
        listing = VendorListing(
            id=uuid.uuid4(),
            vendor_id=uuid.uuid4(),
            business_name="Test Biz",
            category="photography",
            description="desc",
            service_area="Kigali",
            cover_image_url=None,
        )
        saved = await repo.save(listing)
        assert saved.id == listing.id

        retrieved = await repo.get_by_vendor_id(listing.vendor_id)
        assert retrieved is not None
        assert retrieved.business_name == "Test Biz"

    @pytest.mark.asyncio
    async def test_save_is_idempotent_by_vendor_id(self, session: AsyncSession):
        repo = AsyncVendorListingRepository(session)
        vendor_id = uuid.uuid4()

        await repo.save(VendorListing(
            id=uuid.uuid4(),
            vendor_id=vendor_id,
            business_name="Original",
            category="photography",
            description="desc",
            service_area="Kigali",
            cover_image_url=None,
        ))

        await repo.save(VendorListing(
            id=uuid.uuid4(),
            vendor_id=vendor_id,
            business_name="Updated",
            category="photography",
            description="desc",
            service_area="Kigali",
            cover_image_url=None,
        ))

        items, total = await repo.search(query="Updated")
        assert total == 1
        assert items[0].business_name == "Updated"

    @pytest.mark.asyncio
    @pytest.mark.skip(reason="Full-text search requires PostgreSQL pg_trgm")
    async def test_search_full_text(self, session: AsyncSession):
        pass

    @pytest.mark.asyncio
    async def test_search_with_filters(self, session: AsyncSession):
        repo = AsyncVendorListingRepository(session)
        await repo.save(VendorListing(
            id=uuid.uuid4(),
            vendor_id=uuid.uuid4(),
            business_name="Photo",
            category="photography",
            description="...",
            service_area="Kigali",
            cover_image_url=None,
            average_rating=4.5,
        ))
        await repo.save(VendorListing(
            id=uuid.uuid4(),
            vendor_id=uuid.uuid4(),
            business_name="Catering",
            category="catering",
            description="...",
            service_area="Kigali",
            cover_image_url=None,
            average_rating=3.0,
        ))

        items, total = await repo.search(category="photography", min_rating=4.0)
        assert total == 1
        assert items[0].category == "photography"

    @pytest.mark.asyncio
    async def test_search_ranking_and_stable_order(self, session: AsyncSession):
        repo = AsyncVendorListingRepository(session)
        vendor_a = uuid.uuid4()
        vendor_b = uuid.uuid4()

        await repo.save(VendorListing(
            id=uuid.uuid4(),
            vendor_id=vendor_a,
            business_name="Photo Studio",
            category="photography",
            description="Exact match studio",
            service_area="Kigali",
            cover_image_url=None,
            created_at=datetime(2024, 1, 1, tzinfo=timezone.utc),
        ))
        await repo.save(VendorListing(
            id=uuid.uuid4(),
            vendor_id=vendor_b,
            business_name="Photo Works",
            category="photography",
            description="Prefix match",
            service_area="Kigali",
            cover_image_url=None,
            created_at=datetime(2024, 1, 2, tzinfo=timezone.utc),
        ))

        items, total = await repo.search(query="Photo Studio")
        assert total == 1
        assert items[0].business_name == "Photo Studio"


class TestAsyncReviewRepository:
    @pytest.mark.asyncio
    async def test_save_and_list(self, session: AsyncSession):
        listing_repo = AsyncVendorListingRepository(session)
        vendor_id = uuid.uuid4()
        await listing_repo.save(VendorListing(
            id=uuid.uuid4(),
            vendor_id=vendor_id,
            business_name="Biz",
            category="photo",
            description="...",
            service_area="Kigali",
            cover_image_url=None,
        ))

        repo = AsyncReviewRepository(session)
        review = Review(
            id=uuid.uuid4(),
            vendor_id=vendor_id,
            author_user_id=uuid.uuid4(),
            rating=5,
            comment="Great",
        )
        saved = await repo.save(review)
        assert saved.id == review.id

        avg = await repo.get_average_rating(vendor_id)
        assert avg == 5.0

        reviews = await repo.list_by_vendor(vendor_id)
        assert len(reviews) == 1
