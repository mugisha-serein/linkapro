from fastapi import Depends
from sqlalchemy.ext.asyncio import AsyncSession

from fastapi_app.database import get_session
from fastapi_app.repositories import (
    AsyncVendorListingRepository,
    AsyncReviewRepository,
)
from application.marketplace.handlers import (
    MarketplaceCommandHandlers,
    MarketplaceQueryHandlers,
)
from infrastructure.adapters.fastapi_event_dispatcher import FastAPIEventDispatcher


async def get_listing_repo(
    session: AsyncSession = Depends(get_session),
) -> AsyncVendorListingRepository:
    return AsyncVendorListingRepository(session)


async def get_review_repo(
    session: AsyncSession = Depends(get_session),
) -> AsyncReviewRepository:
    return AsyncReviewRepository(session)


async def get_command_handlers(
    listing_repo: AsyncVendorListingRepository = Depends(get_listing_repo),
    review_repo: AsyncReviewRepository = Depends(get_review_repo),
) -> MarketplaceCommandHandlers:
    return MarketplaceCommandHandlers(
        listing_repo=listing_repo,
        review_repo=review_repo,
        event_dispatcher=FastAPIEventDispatcher(),
    )


async def get_query_handlers(
    listing_repo: AsyncVendorListingRepository = Depends(get_listing_repo),
    review_repo: AsyncReviewRepository = Depends(get_review_repo),
) -> MarketplaceQueryHandlers:
    return MarketplaceQueryHandlers(
        listing_repo=listing_repo,
        review_repo=review_repo,
    )