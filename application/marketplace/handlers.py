import uuid
from typing import Optional, Tuple, List

from domain.marketplace.entities import VendorListing, Review
from domain.marketplace.interfaces import IVendorListingRepository, IReviewRepository
from domain.marketplace.events import VendorListingUpdated, ReviewPosted
from domain.shared.utils import utc_now
from .commands import UpdateVendorListingCommand, PostReviewCommand
from .queries import SearchVendorsQuery, GetVendorListingQuery, GetVendorReviewsQuery
from .dtos import VendorListingDTO, ReviewDTO, SearchResultDTO


class MarketplaceCommandHandlers:
    def __init__(
        self,
        listing_repo: IVendorListingRepository,
        review_repo: IReviewRepository,
        event_dispatcher,
    ):
        self.listing_repo = listing_repo
        self.review_repo = review_repo
        self.event_dispatcher = event_dispatcher

    async def update_vendor_listing(self, cmd: UpdateVendorListingCommand) -> VendorListingDTO:
        listing = await self.listing_repo.get_by_vendor_id(cmd.vendor_id)
        if not listing:
            # Create new listing projection
            listing = VendorListing(
                id=uuid.uuid4(),
                vendor_id=cmd.vendor_id,
                business_name=cmd.business_name or "",
                category=cmd.category or "other",
                description=cmd.description or "",
                service_area=cmd.service_area or "",
                cover_image_url=cmd.cover_image_url,
            )
        else:
            if cmd.business_name is not None:
                listing.business_name = cmd.business_name
            if cmd.category is not None:
                listing.category = cmd.category
            if cmd.description is not None:
                listing.description = cmd.description
            if cmd.service_area is not None:
                listing.service_area = cmd.service_area
            if cmd.cover_image_url is not None:
                listing.cover_image_url = cmd.cover_image_url
            listing.updated_at = utc_now()

        saved = await self.listing_repo.save(listing)
        self.event_dispatcher.dispatch(VendorListingUpdated(vendor_id=saved.vendor_id, occurred_at=utc_now()))
        return self._to_listing_dto(saved)

    async def post_review(self, cmd: PostReviewCommand) -> ReviewDTO:
        listing = await self.listing_repo.get_by_vendor_id(cmd.vendor_id)
        if not listing:
            raise ValueError("Vendor not found")
        review = Review(
            id=uuid.uuid4(),
            vendor_id=cmd.vendor_id,
            author_user_id=cmd.author_user_id,
            rating=cmd.rating,
            comment=cmd.comment,
        )
        saved = await self.review_repo.save(review)
        self.event_dispatcher.dispatch(ReviewPosted(
            review_id=saved.id, vendor_id=saved.vendor_id, rating=saved.rating, occurred_at=utc_now()
        ))
        return self._to_review_dto(saved)

    @staticmethod
    def _to_listing_dto(l: VendorListing) -> VendorListingDTO:
        return VendorListingDTO(
            id=str(l.vendor_id),
            business_name=l.business_name,
            category=l.category,
            description=l.description,
            service_area=l.service_area,
            cover_image_url=l.cover_image_url,
            average_rating=l.average_rating,
            total_reviews=l.total_reviews,
            is_verified=l.is_verified,
        )

    @staticmethod
    def _to_review_dto(r: Review) -> ReviewDTO:
        return ReviewDTO(
            id=str(r.id),
            vendor_id=str(r.vendor_id),
            author_user_id=str(r.author_user_id),
            rating=r.rating,
            comment=r.comment,
            created_at=r.created_at,
        )


class MarketplaceQueryHandlers:
    def __init__(self, listing_repo: IVendorListingRepository, review_repo: IReviewRepository):
        self.listing_repo = listing_repo
        self.review_repo = review_repo

    async def search_vendors(self, query: SearchVendorsQuery) -> SearchResultDTO:
        raise RuntimeError("Legacy marketplace search handler is disabled.")

    async def get_vendor_listing(self, query: GetVendorListingQuery) -> Optional[VendorListingDTO]:
        vendor_id = uuid.UUID(query.vendor_id)
        listing = await self.listing_repo.get_by_vendor_id(vendor_id)
        if not listing:
            return None
        return MarketplaceCommandHandlers._to_listing_dto(listing)

    async def get_vendor_reviews(self, query: GetVendorReviewsQuery) -> Tuple[List[ReviewDTO], int]:
        vendor_id = uuid.UUID(query.vendor_id)
        offset = (query.page - 1) * query.page_size
        reviews = await self.review_repo.list_by_vendor(vendor_id, limit=query.page_size, offset=offset)
        dtos = [MarketplaceCommandHandlers._to_review_dto(r) for r in reviews]
        # For simplicity, total count not implemented in repo; would need separate count query
        total = len(dtos)
        return dtos, total
