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

        retrieved = await repo.get_by_vendor_id(vendor_id)
        assert retrieved is not None
        assert retrieved.business_name == "Updated"

    @pytest.mark.asyncio
    @pytest.mark.skip(reason="Full-text search requires PostgreSQL pg_trgm")
    async def test_search_full_text(self, session: AsyncSession):
        pass

    @pytest.mark.asyncio
    async def test_legacy_search_path_is_disabled(self, session: AsyncSession):
        repo = AsyncVendorListingRepository(session)
        with pytest.raises(RuntimeError, match="Legacy marketplace search path is disabled"):
            await repo.search(category="photography", min_rating=4.0)


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
