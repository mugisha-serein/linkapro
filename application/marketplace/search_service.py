import hashlib
import json
import logging
import re
import time
from dataclasses import asdict, dataclass
from decimal import Decimal
from typing import Optional

from redis.asyncio import Redis
from redis.exceptions import RedisError

from application.marketplace.dtos import SearchResultDTO, VendorListingDTO
from domain.marketplace.entities import VendorListing
from domain.marketplace.interfaces import IVendorListingRepository

logger = logging.getLogger(__name__)

MAX_PAGE_SIZE = 50
MAX_PAGE_NUMBER = 1000
CACHE_NAMESPACE = "marketplace:search"
CACHE_VERSION_KEY = "marketplace:search:version"
RATE_LIMIT_NAMESPACE = "marketplace:search:rate"


@dataclass(frozen=True)
class MarketplaceSearchCriteria:
    query: Optional[str] = None
    category: Optional[str] = None
    location: Optional[str] = None
    min_rating: Optional[float] = None
    min_price: Optional[Decimal] = None
    max_price: Optional[Decimal] = None
    page: int = 1
    page_size: int = 20


@dataclass(frozen=True)
class MarketplaceSearchResultPayload:
    items: list[dict]
    total: int
    page: int
    page_size: int
    total_pages: int


class MarketplaceSearchCache:
    def __init__(
        self,
        redis_client: Redis,
        ttl_seconds: int,
        rate_limit_requests: int,
        rate_limit_window_seconds: int,
    ) -> None:
        self.redis_client = redis_client
        self.ttl_seconds = ttl_seconds
        self.rate_limit_requests = rate_limit_requests
        self.rate_limit_window_seconds = rate_limit_window_seconds

    async def get_version(self) -> int:
        current = await self.redis_client.get(CACHE_VERSION_KEY)
        if current is None:
            await self.redis_client.set(CACHE_VERSION_KEY, "1", nx=True)
            current = await self.redis_client.get(CACHE_VERSION_KEY)
        return int(current or 1)

    async def invalidate(self) -> int:
        version = await self.redis_client.incr(CACHE_VERSION_KEY)
        return int(version)

    def build_cache_key(self, criteria: MarketplaceSearchCriteria, version: int) -> str:
        normalized = {
            "query": self._normalize(criteria.query),
            "category": self._normalize(criteria.category),
            "location": self._normalize(criteria.location),
            "min_rating": criteria.min_rating,
            "min_price": str(criteria.min_price) if criteria.min_price is not None else None,
            "max_price": str(criteria.max_price) if criteria.max_price is not None else None,
            "page": criteria.page,
            "page_size": criteria.page_size,
        }
        payload = json.dumps(normalized, sort_keys=True, separators=(",", ":"))
        digest = hashlib.sha256(payload.encode("utf-8")).hexdigest()
        return f"{CACHE_NAMESPACE}:v{version}:{digest}"

    async def get_cached_result(self, cache_key: str) -> Optional[MarketplaceSearchResultPayload]:
        raw = await self.redis_client.get(cache_key)
        if not raw:
            return None
        payload = json.loads(raw)
        return MarketplaceSearchResultPayload(**payload)

    async def set_cached_result(self, cache_key: str, result: SearchResultDTO) -> None:
        payload = self._serialize_result(result)
        await self.redis_client.set(cache_key, json.dumps(payload, separators=(",", ":")), ex=self.ttl_seconds)

    async def enforce_rate_limit(self, client_id: str) -> None:
        window_bucket = int(time.time() // self.rate_limit_window_seconds)
        key = f"{RATE_LIMIT_NAMESPACE}:{client_id}:{window_bucket}"
        current = await self.redis_client.incr(key)
        if current == 1:
            await self.redis_client.expire(key, self.rate_limit_window_seconds)
        if current > self.rate_limit_requests:
            logger.warning(
                "Marketplace search rate limit exceeded",
                extra={
                    "client_id": client_id,
                    "window_bucket": window_bucket,
                    "request_count": current,
                    "limit": self.rate_limit_requests,
                },
            )
            raise RuntimeError(
                "Marketplace search rate limit exceeded."
            )

    @staticmethod
    def _normalize(value: Optional[str]) -> Optional[str]:
        if not value:
            return None
        normalized = re.sub(r"\s+", " ", value.strip()).lower()
        return normalized or None

    @staticmethod
    def _serialize_result(result: SearchResultDTO) -> dict:
        payload = asdict(result)
        for item in payload["items"]:
            for field in ("starting_price", "min_package_price", "max_package_price"):
                if item.get(field) is not None:
                    item[field] = str(item[field])
        return payload


class MarketplaceSearchService:
    def __init__(self, listing_repo: IVendorListingRepository, cache: MarketplaceSearchCache | None) -> None:
        self.listing_repo = listing_repo
        self.cache = cache

    async def search(
        self,
        criteria: MarketplaceSearchCriteria,
        client_id: str,
    ) -> SearchResultDTO:
        started = time.perf_counter()
        normalized = self._normalize_criteria(criteria)
        logger.info(
            "Marketplace search requested",
            extra={
                "query": normalized.query,
                "category": normalized.category,
                "location": normalized.location,
                "page": normalized.page,
                "page_size": normalized.page_size,
                "min_rating": normalized.min_rating,
                "min_price": str(normalized.min_price) if normalized.min_price is not None else None,
                "max_price": str(normalized.max_price) if normalized.max_price is not None else None,
            },
        )
        cache_key = None
        if self.cache is not None:
            try:
                await self.cache.enforce_rate_limit(client_id)
                cache_version = await self.cache.get_version()
                cache_key = self.cache.build_cache_key(normalized, cache_version)
                cached = await self.cache.get_cached_result(cache_key)
                if cached is not None:
                    elapsed_ms = round((time.perf_counter() - started) * 1000, 2)
                    logger.info(
                        "Marketplace search completed",
                        extra={
                            "query": normalized.query,
                            "category": normalized.category,
                            "location": normalized.location,
                            "page": normalized.page,
                            "page_size": normalized.page_size,
                            "cache_hit": True,
                            "result_count": len(cached.items),
                            "elapsed_ms": elapsed_ms,
                            "ranking_method": self._ranking_method(normalized),
                        },
                    )
                    return self._payload_to_result(cached)
            except RedisError:
                logger.warning(
                    "marketplace_redis_unavailable",
                    extra={"operation": "read_or_rate_limit"},
                    exc_info=True,
                )
                cache_key = None

        result = await self._execute_search(normalized)
        if self.cache is not None and cache_key is not None:
            try:
                await self.cache.set_cached_result(cache_key, result)
            except RedisError:
                logger.warning(
                    "marketplace_redis_unavailable",
                    extra={"operation": "write"},
                    exc_info=True,
                )

        elapsed_ms = round((time.perf_counter() - started) * 1000, 2)
        logger.info(
            "Marketplace search completed",
            extra={
                "query": normalized.query,
                "category": normalized.category,
                "location": normalized.location,
                "page": normalized.page,
                "page_size": normalized.page_size,
                "cache_hit": False,
                "result_count": len(result.items),
                "elapsed_ms": elapsed_ms,
                "ranking_method": self._ranking_method(normalized),
            },
        )
        return result

    async def _execute_search(self, criteria: MarketplaceSearchCriteria) -> SearchResultDTO:
        limit = max(1, min(criteria.page_size, MAX_PAGE_SIZE))
        offset = max(0, (criteria.page - 1) * limit)
        listings, total = await self.listing_repo.search(
            query=criteria.query,
            category=criteria.category,
            location=criteria.location,
            min_rating=criteria.min_rating,
            min_price=criteria.min_price,
            max_price=criteria.max_price,
            limit=limit,
            offset=offset,
        )
        items = [self._listing_to_dto(listing) for listing in listings]
        total_pages = (total + limit - 1) // limit if total else 0
        return SearchResultDTO(
            items=items,
            total=total,
            page=criteria.page,
            page_size=limit,
            total_pages=total_pages,
        )

    @staticmethod
    def _normalize_criteria(criteria: MarketplaceSearchCriteria) -> MarketplaceSearchCriteria:
        return MarketplaceSearchCriteria(
            query=MarketplaceSearchService._normalize_text(criteria.query),
            category=MarketplaceSearchService._normalize_text(criteria.category),
            location=MarketplaceSearchService._normalize_text(criteria.location),
            min_rating=criteria.min_rating,
            min_price=Decimal(str(criteria.min_price)) if criteria.min_price is not None else None,
            max_price=Decimal(str(criteria.max_price)) if criteria.max_price is not None else None,
            page=max(1, min(criteria.page, MAX_PAGE_NUMBER)),
            page_size=max(1, min(criteria.page_size, MAX_PAGE_SIZE)),
        )

    @staticmethod
    def _normalize_text(value: Optional[str]) -> Optional[str]:
        if not value:
            return None
        if any(not ch.isprintable() for ch in value):
            raise ValueError("Search parameters must contain printable characters only.")
        normalized = re.sub(r"\s+", " ", value.strip()).lower()
        if not normalized:
            return None
        return normalized

    @staticmethod
    def _listing_to_dto(listing: VendorListing) -> VendorListingDTO:
        return VendorListingDTO(
            id=str(listing.vendor_id),
            business_name=listing.business_name,
            category=listing.category,
            description=listing.description,
            service_area=listing.service_area,
            cover_image_url=listing.cover_image_url,
            average_rating=float(listing.average_rating or 0.0),
            total_reviews=int(listing.total_reviews or 0),
            is_verified=bool(listing.is_verified),
            starting_price=listing.starting_price,
            min_package_price=listing.min_package_price,
            max_package_price=listing.max_package_price,
            currency=listing.currency,
        )

    @staticmethod
    def _payload_to_result(payload: MarketplaceSearchResultPayload) -> SearchResultDTO:
        converted_items = []
        for item in payload.items:
            converted = dict(item)
            for field in ("starting_price", "min_package_price", "max_package_price"):
                if converted.get(field) is not None:
                    converted[field] = Decimal(str(converted[field]))
            converted_items.append(VendorListingDTO(**converted))
        return SearchResultDTO(
            items=converted_items,
            total=payload.total,
            page=payload.page,
            page_size=payload.page_size,
            total_pages=payload.total_pages,
        )

    @staticmethod
    def _ranking_method(criteria: MarketplaceSearchCriteria) -> str:
        return "tsvector+boosts"
