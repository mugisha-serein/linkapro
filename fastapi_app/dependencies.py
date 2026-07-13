import hashlib
import logging
from functools import lru_cache

from fastapi import Depends
from fastapi import Request
from sqlalchemy.ext.asyncio import AsyncSession
from redis.asyncio import Redis
from redis.exceptions import RedisError

from application.marketplace.search_service import (
    MarketplaceSearchCache,
    MarketplaceSearchCriteria,
    MarketplaceSearchService,
)
from fastapi_app.database import get_session
from fastapi_app.config import (
    get_bool,
    is_production,
    mask_redis_url_for_logs,
    normalize_redis_url,
    require_env,
    require_int,
)
from fastapi_app.repositories import (
    AsyncVendorListingRepository,
    AsyncReviewRepository,
)
from application.marketplace.handlers import (
    MarketplaceCommandHandlers,
    MarketplaceQueryHandlers,
)
from infrastructure.adapters.fastapi_event_dispatcher import FastAPIEventDispatcher
from fastapi_app.schemas import MarketplaceSearchRequest

logger = logging.getLogger(__name__)


@lru_cache(maxsize=1)
def get_redis_client() -> Redis | None:
    try:
        redis_url = normalize_redis_url(require_env("REDIS_URL"))
        return Redis.from_url(redis_url, decode_responses=True)
    except (RuntimeError, RedisError, ValueError) as exc:
        safe_url = mask_redis_url_for_logs(locals().get("redis_url", ""))
        logger.warning(
            "marketplace_redis_unavailable",
            extra={"reason": exc.__class__.__name__, "redis_url": safe_url},
            exc_info=True,
        )
        return None


def get_marketplace_search_cache() -> MarketplaceSearchCache | None:
    redis_client = get_redis_client()
    if redis_client is None:
        return None
    try:
        ttl_seconds = require_int("FASTAPI_MARKETPLACE_SEARCH_CACHE_TTL_SECONDS", minimum=60, maximum=300)
        rate_limit_requests = require_int("FASTAPI_MARKETPLACE_SEARCH_RATE_LIMIT_REQUESTS", minimum=1)
        rate_limit_window_seconds = require_int("FASTAPI_MARKETPLACE_SEARCH_RATE_LIMIT_WINDOW_SECONDS", minimum=1)
    except RuntimeError:
        logger.warning("Marketplace Redis cache settings are incomplete; search will skip Redis cache and rate limiting.")
        return None
    return MarketplaceSearchCache(
        redis_client=redis_client,
        ttl_seconds=ttl_seconds,
        rate_limit_requests=rate_limit_requests,
        rate_limit_window_seconds=rate_limit_window_seconds,
    )


def get_marketplace_search_params(
    request: Request,
) -> MarketplaceSearchCriteria:
    params = MarketplaceSearchRequest(**dict(request.query_params))
    return MarketplaceSearchCriteria(
        query=params.q,
        category=params.category,
        location=params.location,
        min_rating=params.min_rating if params.min_rating is not None else params.rating,
        min_price=params.min_price,
        max_price=params.max_price,
        page=params.page,
        page_size=params.page_size,
    )


def get_marketplace_client_identifier(request: Request) -> str:
    source = _resolve_client_source(request)
    digest = hashlib.sha256(source.encode("utf-8")).hexdigest()[:32]
    return f"client:{digest}"


def _resolve_client_source(request: Request) -> str:
    trust_proxy_headers = get_bool("FASTAPI_TRUST_PROXY_HEADERS", default=is_production())
    if trust_proxy_headers:
        forwarded_for = request.headers.get("x-forwarded-for")
        forwarded_client = _first_forwarded_for_value(forwarded_for)
        if forwarded_client:
            return forwarded_client

    if request.client and request.client.host:
        return request.client.host
    return "unknown"


def _first_forwarded_for_value(forwarded_for: str | None) -> str | None:
    if not forwarded_for:
        return None
    first = forwarded_for.split(",", 1)[0].strip()
    if not first:
        return None
    if first.startswith("[") and "]" in first:
        return first.split("]", 1)[0].lstrip("[")[:128]
    if first.count(":") == 1 and "." in first:
        return first.split(":", 1)[0][:128]
    return first[:128]


async def get_listing_repo(
    session: AsyncSession = Depends(get_session),
) -> AsyncVendorListingRepository:
    return AsyncVendorListingRepository(session)


async def get_marketplace_search_service(
    listing_repo: AsyncVendorListingRepository = Depends(get_listing_repo),
) -> MarketplaceSearchService:
    return MarketplaceSearchService(
        listing_repo=listing_repo,
        cache=get_marketplace_search_cache(),
    )


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
