import uuid
from decimal import Decimal
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
        min_price: Optional[Decimal] = None,
        max_price: Optional[Decimal] = None,
        limit: int = 20,
        offset: int = 0,
    ) -> Tuple[List[VendorListing], int]:
        normalized_query = self._sanitize_query(query)
        normalized_category = self._sanitize_filter(category)
        normalized_location = self._sanitize_filter(location)
        limit = max(1, min(limit, MAX_PAGE_SIZE))
        offset = max(0, offset)

        conditions = [
            VendorListingModel.approval_status == "approved",
            VendorListingModel.is_verified.is_(True),
        ]
        ts_query = None
        if normalized_query:
            if self._uses_postgresql():
                ts_query = func.plainto_tsquery("simple", normalized_query)
                conditions.append(VendorListingModel.search_vector.op("@@")(ts_query))
            else:
                pattern = f"%{normalized_query}%"
                conditions.append(
                    or_(
                        func.lower(VendorListingModel.business_name).like(pattern),
                        func.lower(VendorListingModel.description).like(pattern),
                        func.lower(VendorListingModel.category).like(pattern),
                        func.lower(VendorListingModel.service_area).like(pattern),
                    )
                )
        if normalized_category:
            conditions.append(func.lower(VendorListingModel.category) == normalized_category)
        if normalized_location:
            conditions.append(func.lower(VendorListingModel.service_area).like(f"%{normalized_location}%"))
        if min_rating is not None:
            conditions.append(VendorListingModel.average_rating >= min_rating)
        if min_price is not None:
            conditions.append(VendorListingModel.min_package_price >= min_price)
        if max_price is not None:
            conditions.append(VendorListingModel.min_package_price <= max_price)

        where_clause = and_(*conditions)
        rank_expression = self._rank_expression(
            query_text=normalized_query,
            normalized_category=normalized_category,
            normalized_location=normalized_location,
            ts_query=ts_query,
        ).label("search_rank")

        count_stmt = select(func.count()).select_from(VendorListingModel).where(where_clause)
        total_result = await self.session.execute(count_stmt)
        total = int(total_result.scalar_one())

        data_stmt = (
            select(VendorListingModel)
            .where(where_clause)
            .order_by(rank_expression.desc(), VendorListingModel.id.desc())
            .limit(limit)
            .offset(offset)
        )
        rows = await self.session.execute(data_stmt)
        return [self._to_domain(model) for model in rows.scalars().all()], total

    async def save(self, listing: VendorListing) -> VendorListing:
        result = await self.session.execute(
            select(VendorListingModel).where(VendorListingModel.vendor_id == listing.vendor_id)
        )
        model = result.scalar_one_or_none()
        if model is None:
            model = VendorListingModel(id=listing.id, vendor_id=listing.vendor_id)
            self.session.add(model)

        model.external_id = getattr(listing, "external_id", None)
        model.business_name = listing.business_name
        model.category = listing.category
        model.description = listing.description
        model.service_area = listing.service_area
        model.cover_image_url = listing.cover_image_url
        model.average_rating = listing.average_rating
        model.total_reviews = listing.total_reviews
        model.is_verified = listing.is_verified
        model.approval_status = "approved"
        model.search_rank_score = getattr(listing, "search_rank_score", 0.0)
        model.starting_price = listing.starting_price
        model.min_package_price = listing.min_package_price
        model.max_package_price = listing.max_package_price
        model.currency = listing.currency
        model.created_at = listing.created_at
        model.updated_at = listing.updated_at
        await self.session.commit()
        await self.session.refresh(model)
        return self._to_domain(model)

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
            starting_price=model.starting_price,
            min_package_price=model.min_package_price,
            max_package_price=model.max_package_price,
            currency=model.currency,
            created_at=model.created_at,
            updated_at=model.updated_at,
        )

    def _rank_expression(
        self,
        *,
        query_text: Optional[str],
        normalized_category: Optional[str],
        normalized_location: Optional[str],
        ts_query,
    ):
        if ts_query is not None:
            text_rank = func.coalesce(func.ts_rank_cd(VendorListingModel.search_vector, ts_query), 0.0)
        elif query_text:
            pattern = f"%{query_text}%"
            text_rank = case(
                (func.lower(VendorListingModel.business_name).like(pattern), 1.0),
                (func.lower(VendorListingModel.description).like(pattern), 0.5),
                else_=0.0,
            )
        else:
            text_rank = 0.0
        exact_name_boost = case(
            (func.lower(VendorListingModel.business_name) == query_text, 4.0),
            else_=0.0,
        )
        category_boost = case(
            (func.lower(VendorListingModel.category) == normalized_category, 2.0),
            else_=0.0,
        )
        location_boost = case(
            (func.lower(VendorListingModel.service_area) == normalized_location, 1.5),
            else_=0.0,
        )
        rating_boost = func.coalesce(VendorListingModel.average_rating, 0.0) * 0.5
        return (
            func.coalesce(text_rank, 0.0) * 10.0
            + exact_name_boost
            + category_boost
            + location_boost
            + rating_boost
        )

    def _uses_postgresql(self) -> bool:
        bind = self.session.get_bind()
        return bool(bind and bind.dialect.name == "postgresql")

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
        try:
            self.session.add(model)
            await self.session.flush()
            await self._update_vendor_rating(review.vendor_id)
            await self.session.commit()
        except Exception:
            await self.session.rollback()
            raise
        await self.session.refresh(model)
        return self._to_domain(model)

    async def delete(self, review_id: uuid.UUID) -> None:
        model = await self.session.get(ReviewModel, review_id)
        if model:
            vendor_id = model.vendor_id
            try:
                await self.session.delete(model)
                await self.session.flush()
                await self._update_vendor_rating(vendor_id)
                await self.session.commit()
            except Exception:
                await self.session.rollback()
                raise

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
