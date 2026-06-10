import uuid
from typing import Optional, List, Tuple
from sqlalchemy import select, func, and_, or_, case
from sqlalchemy.ext.asyncio import AsyncSession

from domain.marketplace.entities import VendorListing, Review
from domain.marketplace.interfaces import IVendorListingRepository, IReviewRepository
from fastapi_app.marketplace.models import VendorListingModel, ReviewModel

MAX_PAGE_SIZE = 50


class AsyncVendorListingRepository(IVendorListingRepository):
    def __init__(self, session: AsyncSession):
        self.session = session

    async def get_by_vendor_id(self, vendor_id: uuid.UUID) -> Optional[VendorListing]:
        stmt = select(VendorListingModel).where(VendorListingModel.vendor_id == vendor_id)
        stmt = stmt.where(VendorListingModel.approval_status == "approved")
        result = await self.session.execute(stmt)
        model = result.scalar_one_or_none()
        return self._to_domain(model) if model else None

    async def search(
        self,
        query: Optional[str] = None,
        category: Optional[str] = None,
        location: Optional[str] = None,
        min_rating: Optional[float] = None,
        min_price: Optional[float] = None,
        max_price: Optional[float] = None,
        limit: int = 20,
        offset: int = 0,
    ) -> Tuple[List[VendorListing], int]:
        raise RuntimeError("Legacy marketplace search path is disabled.")

    async def save(self, listing: VendorListing) -> VendorListing:
        model = VendorListingModel(
            id=listing.id,
            vendor_id=listing.vendor_id,
            external_id=getattr(listing, "external_id", None),
            business_name=listing.business_name,
            category=listing.category,
            description=listing.description,
            service_area=listing.service_area,
            cover_image_url=listing.cover_image_url,
            average_rating=listing.average_rating,
            total_reviews=listing.total_reviews,
            is_verified=listing.is_verified,
            approval_status="approved",
            search_rank_score=getattr(listing, "search_rank_score", 0.0),
            created_at=listing.created_at,
            updated_at=listing.updated_at,
        )
        merged = await self.session.merge(model)
        await self.session.commit()
        return self._to_domain(merged)

    async def delete(self, vendor_id: uuid.UUID) -> None:
        stmt = select(VendorListingModel).where(VendorListingModel.vendor_id == vendor_id)
        result = await self.session.execute(stmt)
        model = result.scalar_one_or_none()
        if model:
            await self.session.delete(model)
            await self.session.commit()

    def _to_domain(self, model: VendorListingModel) -> VendorListing:
        return VendorListing(
            id=model.id,
            vendor_id=model.vendor_id,
            business_name=model.business_name,
            category=model.category,
            description=model.description,
            service_area=model.service_area,
            cover_image_url=model.cover_image_url,
            average_rating=model.average_rating,
            total_reviews=model.total_reviews,
            is_verified=model.is_verified,
            created_at=model.created_at,
            updated_at=model.updated_at,
        )

    @staticmethod
    def _sanitize_query(query: Optional[str]) -> Optional[str]:
        if not query:
            return None
        normalized = " ".join(query.strip().split()).lower()
        return normalized[:128] or None

    @staticmethod
    def _sanitize_filter(value: Optional[str]) -> Optional[str]:
        if not value:
            return None
        normalized = " ".join(value.strip().split()).lower()
        return normalized[:64] or None


class AsyncReviewRepository(IReviewRepository):
    def __init__(self, session: AsyncSession):
        self.session = session

    async def get_by_id(self, review_id: uuid.UUID) -> Optional[Review]:
        stmt = select(ReviewModel).where(ReviewModel.id == review_id)
        result = await self.session.execute(stmt)
        model = result.scalar_one_or_none()
        return self._to_domain(model) if model else None

    async def list_by_vendor(self, vendor_id: uuid.UUID, limit: int = 20, offset: int = 0) -> List[Review]:
        stmt = select(ReviewModel).where(ReviewModel.vendor_id == vendor_id).order_by(ReviewModel.created_at.desc()).limit(limit).offset(offset)
        result = await self.session.execute(stmt)
        models = result.scalars().all()
        return [self._to_domain(m) for m in models]

    async def save(self, review: Review) -> Review:
        model = ReviewModel(
            id=review.id,
            vendor_id=review.vendor_id,
            author_user_id=review.author_user_id,
            rating=review.rating,
            comment=review.comment,
            is_verified_purchase=review.is_verified_purchase,
            created_at=review.created_at,
        )
        self.session.add(model)
        await self.session.commit()
        await self.session.refresh(model)
        # Update vendor listing average rating (could be done via event handler)
        await self._update_vendor_rating(review.vendor_id)
        return self._to_domain(model)

    async def delete(self, review_id: uuid.UUID) -> None:
        model = await self.session.get(ReviewModel, review_id)
        if model:
            vendor_id = model.vendor_id
            await self.session.delete(model)
            await self.session.commit()
            await self._update_vendor_rating(vendor_id)

    async def get_average_rating(self, vendor_id: uuid.UUID) -> float:
        stmt = select(func.avg(ReviewModel.rating)).where(ReviewModel.vendor_id == vendor_id)
        result = await self.session.execute(stmt)
        avg = result.scalar()
        return float(avg) if avg else 0.0

    async def _update_vendor_rating(self, vendor_id: uuid.UUID):
        avg_rating = await self.get_average_rating(vendor_id)
        count_stmt = select(func.count()).where(ReviewModel.vendor_id == vendor_id)
        result = await self.session.execute(count_stmt)
        total_reviews = result.scalar_one()
        stmt = select(VendorListingModel).where(VendorListingModel.vendor_id == vendor_id)
        result = await self.session.execute(stmt)
        listing = result.scalar_one_or_none()
        if listing:
            listing.average_rating = avg_rating
            listing.total_reviews = total_reviews
            await self.session.commit()

    def _to_domain(self, model: ReviewModel) -> Review:
        return Review(
            id=model.id,
            vendor_id=model.vendor_id,
            author_user_id=model.author_user_id,
            rating=model.rating,
            comment=model.comment,
            is_verified_purchase=model.is_verified_purchase,
            created_at=model.created_at,
        )
