import uuid
import pytest
from datetime import datetime, timezone
from decimal import Decimal
from sqlalchemy import delete, select
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
    async def test_search_filters_visible_listings_and_returns_pricing(self, session: AsyncSession):
        await session.execute(delete(ReviewModel))
        await session.execute(delete(VendorListingModel))
        await session.commit()
        vendor_id = uuid.uuid4()
        hidden_vendor_id = uuid.uuid4()
        session.add_all(
            [
                VendorListingModel(
                    vendor_id=vendor_id,
                    business_name="Visible Photographer",
                    category="photography",
                    description="Approved listing",
                    service_area="Kigali, Rwanda",
                    approval_status="approved",
                    is_verified=True,
                    average_rating=4.8,
                    starting_price=Decimal("10000.00"),
                    min_package_price=Decimal("10000.00"),
                    max_package_price=Decimal("20000.00"),
                    currency="RWF",
                ),
                VendorListingModel(
                    vendor_id=hidden_vendor_id,
                    business_name="Hidden Photographer",
                    category="photography",
                    description="Rejected listing",
                    service_area="Kigali, Rwanda",
                    approval_status="rejected",
                    is_verified=True,
                    average_rating=5.0,
                    min_package_price=Decimal("5000.00"),
                ),
            ]
        )
        await session.commit()

        repo = AsyncVendorListingRepository(session)
        listings, total = await repo.search(category="photography", min_rating=4.0, max_price=Decimal("15000.00"))

        assert total == 1
        assert [listing.vendor_id for listing in listings] == [vendor_id]
        assert listings[0].starting_price == Decimal("10000.00")
        assert listings[0].currency == "RWF"


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

    @pytest.mark.asyncio
    async def test_save_commits_review_and_rating_update_once(self, session: AsyncSession):
        counting_session = CountingAsyncSession(session)
        listing_repo = AsyncVendorListingRepository(counting_session)
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
        counting_session.commit_count = 0

        repo = AsyncReviewRepository(counting_session)
        await repo.save(Review(
            id=uuid.uuid4(),
            vendor_id=vendor_id,
            author_user_id=uuid.uuid4(),
            rating=4,
            comment="Good",
        ))

        listing = await session.scalar(select(VendorListingModel).where(VendorListingModel.vendor_id == vendor_id))
        assert counting_session.commit_count == 1
        assert listing.average_rating == 4.0
        assert listing.total_reviews == 1


class CountingAsyncSession:
    def __init__(self, wrapped: AsyncSession):
        self.wrapped = wrapped
        self.commit_count = 0

    def add(self, *args, **kwargs):
        return self.wrapped.add(*args, **kwargs)

    async def commit(self):
        self.commit_count += 1
        return await self.wrapped.commit()

    async def rollback(self):
        return await self.wrapped.rollback()

    async def refresh(self, *args, **kwargs):
        return await self.wrapped.refresh(*args, **kwargs)

    async def flush(self, *args, **kwargs):
        return await self.wrapped.flush(*args, **kwargs)

    async def execute(self, *args, **kwargs):
        return await self.wrapped.execute(*args, **kwargs)

    async def get(self, *args, **kwargs):
        return await self.wrapped.get(*args, **kwargs)

    async def delete(self, *args, **kwargs):
        return await self.wrapped.delete(*args, **kwargs)

    def get_bind(self):
        return self.wrapped.get_bind()
