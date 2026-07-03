import uuid
import pytest
from datetime import datetime, timezone
from httpx import AsyncClient, ASGITransport
from unittest.mock import AsyncMock, Mock
from redis.exceptions import RedisError
from sqlalchemy import delete, func, select
from sqlalchemy.exc import SQLAlchemyError
from sqlalchemy.ext.asyncio import AsyncSession

from fastapi_app.main import app
from fastapi_app.dependencies import get_query_handlers, get_command_handlers, get_marketplace_search_service
from fastapi_app.database import get_session
from fastapi_app.config import get_cors_origins, normalize_database_url, normalize_redis_url
from fastapi_app.marketplace.models import ReviewModel, VendorListingModel
from application.marketplace.search_service import MarketplaceSearchCache, MarketplaceSearchCriteria, MarketplaceSearchService
from application.marketplace.dtos import ReviewDTO, SearchResultDTO, VendorListingDTO


@pytest.fixture
def mock_query_handlers():
    return AsyncMock()


@pytest.fixture
def mock_command_handlers():
    return AsyncMock()


@pytest.fixture
def test_app(mock_query_handlers, mock_command_handlers):
    app.dependency_overrides[get_query_handlers] = lambda: mock_query_handlers
    app.dependency_overrides[get_command_handlers] = lambda: mock_command_handlers
    yield app
    app.dependency_overrides.clear()


@pytest.mark.asyncio
async def test_post_review_requires_authenticated_django_context(test_app):
    vendor_id = str(uuid.uuid4())

    transport = ASGITransport(app=test_app)
    async with AsyncClient(transport=transport, base_url="http://test") as client:
        response = await client.post(
            f"/api/v1/marketplace/vendors/{vendor_id}/reviews",
            json={"author_user_id": str(uuid.uuid4()), "rating": 5, "comment": "Nice"},
        )

    assert response.status_code == 403


@pytest.mark.asyncio
async def test_public_reviews_hide_author_user_id(test_app, mock_query_handlers):
    vendor_id = str(uuid.uuid4())
    mock_query_handlers.get_vendor_listing.return_value = Mock()
    mock_query_handlers.get_vendor_reviews.return_value = (
        [
            ReviewDTO(
                id=str(uuid.uuid4()),
                vendor_id=vendor_id,
                author_user_id=str(uuid.uuid4()),
                rating=5,
                comment="Excellent service",
                created_at=datetime.now(timezone.utc),
            )
        ],
        1,
    )

    transport = ASGITransport(app=test_app)
    async with AsyncClient(transport=transport, base_url="http://test") as client:
        response = await client.get(f"/api/v1/marketplace/vendors/{vendor_id}/reviews")

    assert response.status_code == 200
    assert response.json()[0]["author_display_name"] == "Verified customer"
    assert "author_user_id" not in response.json()[0]


class FakeSearchService:
    def __init__(self, result: SearchResultDTO | None = None, error: Exception | None = None):
        self.result = result
        self.error = error
        self.seen_query = "unset"

    async def search(self, criteria, client_id: str):
        self.seen_query = criteria.query
        if self.error:
            raise self.error
        return self.result or SearchResultDTO(items=[], total=0, page=criteria.page, page_size=criteria.page_size, total_pages=0)


@pytest.mark.asyncio
async def test_search_empty_q_returns_valid_empty_response():
    service = FakeSearchService()
    app.dependency_overrides[get_marketplace_search_service] = lambda: service
    transport = ASGITransport(app=app)
    try:
        async with AsyncClient(transport=transport, base_url="http://test") as client:
            response = await client.get("/api/v1/marketplace/search?page=1&page_size=12&q=")
    finally:
        app.dependency_overrides.clear()

    assert response.status_code == 200
    assert response.json() == {"items": [], "total": 0, "page": 1, "page_size": 12, "total_pages": 0}
    assert service.seen_query is None


@pytest.mark.asyncio
async def test_search_can_return_approved_vendor():
    vendor_id = str(uuid.uuid4())
    service = FakeSearchService(
        SearchResultDTO(
            items=[
                VendorListingDTO(
                    id=str(uuid.uuid4()),
                    business_name="Approved Vendor",
                    category="photography",
                    description="Visible listing",
                    service_area="Kigali",
                    cover_image_url=None,
                    average_rating=0.0,
                    total_reviews=0,
                    is_verified=True,
                )
            ],
            total=1,
            page=1,
            page_size=12,
            total_pages=1,
        )
    )
    app.dependency_overrides[get_marketplace_search_service] = lambda: service
    transport = ASGITransport(app=app)
    try:
        async with AsyncClient(transport=transport, base_url="http://test") as client:
            response = await client.get("/api/v1/marketplace/search?page=1&page_size=12")
    finally:
        app.dependency_overrides.clear()

    assert response.status_code == 200
    assert response.json()["total"] == 1
    assert response.json()["items"][0]["business_name"] == "Approved Vendor"


@pytest.mark.asyncio
async def test_search_database_failure_returns_controlled_503():
    service = FakeSearchService(error=SQLAlchemyError("database unavailable"))
    app.dependency_overrides[get_marketplace_search_service] = lambda: service
    transport = ASGITransport(app=app)
    try:
        async with AsyncClient(transport=transport, base_url="http://test") as client:
            response = await client.get(
                "/api/v1/marketplace/search?page=1&q=",
                headers={"Origin": "https://linkapro.vercel.app"},
            )
    finally:
        app.dependency_overrides.clear()

    assert response.status_code == 503
    assert response.headers["access-control-allow-origin"] == "https://linkapro.vercel.app"
    assert response.json()["detail"]["message"] == "Marketplace search is temporarily unavailable."
    assert response.json()["detail"]["request_id"]


@pytest.mark.asyncio
async def test_search_error_includes_cors_for_custom_domain():
    service = FakeSearchService(error=SQLAlchemyError("database unavailable"))
    app.dependency_overrides[get_marketplace_search_service] = lambda: service
    transport = ASGITransport(app=app)
    try:
        async with AsyncClient(transport=transport, base_url="http://test") as client:
            response = await client.get(
                "/api/v1/marketplace/search?page=1&q=",
                headers={"Origin": "https://www.linkapro.rw"},
            )
    finally:
        app.dependency_overrides.clear()

    assert response.status_code == 503
    assert response.headers["access-control-allow-origin"] == "https://www.linkapro.rw"
    assert response.json()["detail"]["request_id"]


@pytest.mark.asyncio
async def test_cors_preflight_allows_primary_production_origin():
    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://test") as client:
        response = await client.options(
            "/api/v1/marketplace/search?page=1&q=",
            headers={
                "Origin": "https://linkapro.vercel.app",
                "Access-Control-Request-Method": "GET",
            },
        )

    assert response.status_code == 200
    assert response.headers["access-control-allow-origin"] == "https://linkapro.vercel.app"


@pytest.mark.asyncio
async def test_cors_preflight_allows_linkapro_custom_domain():
    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://test") as client:
        response = await client.options(
            "/api/v1/marketplace/search?page=1&q=",
            headers={
                "Origin": "https://www.linkapro.rw",
                "Access-Control-Request-Method": "GET",
            },
        )

    assert response.status_code == 200
    assert response.headers["access-control-allow-origin"] == "https://www.linkapro.rw"


@pytest.mark.asyncio
async def test_cors_preflight_allows_frontend_production_origin():
    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://test") as client:
        response = await client.options(
            "/api/v1/marketplace/search?page=1&q=",
            headers={
                "Origin": "https://linkapro-frontend.vercel.app",
                "Access-Control-Request-Method": "GET",
            },
        )

    assert response.status_code == 200
    assert response.headers["access-control-allow-origin"] == "https://linkapro-frontend.vercel.app"


@pytest.mark.asyncio
async def test_cors_preflight_rejects_unallowed_origin():
    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://test") as client:
        response = await client.options(
            "/api/v1/marketplace/search?page=1&q=",
            headers={
                "Origin": "https://example.com",
                "Access-Control-Request-Method": "GET",
            },
        )

    assert response.status_code == 400
    assert "access-control-allow-origin" not in response.headers


@pytest.mark.asyncio
async def test_marketplace_health_reports_listing_counts(session: AsyncSession):
    await session.execute(delete(VendorListingModel))
    await session.commit()

    session.add_all(
        [
            VendorListingModel(
                vendor_id=uuid.uuid4(),
                business_name="Approved",
                category="photography",
                description="Visible listing",
                service_area="Kigali",
                approval_status="approved",
            ),
            VendorListingModel(
                vendor_id=uuid.uuid4(),
                business_name="Rejected",
                category="photography",
                description="Hidden listing",
                service_area="Kigali",
                approval_status="rejected",
            ),
        ]
    )
    await session.commit()

    async def override_session():
        yield session

    app.dependency_overrides[get_session] = override_session
    transport = ASGITransport(app=app)
    try:
        async with AsyncClient(transport=transport, base_url="http://test") as client:
            response = await client.get("/api/v1/marketplace/health")
    finally:
        app.dependency_overrides.clear()

    assert response.status_code == 200
    assert response.json() == {
        "status": "ok",
        "listings_count": 2,
        "approved_listings_count": 1,
    }


@pytest.mark.asyncio
async def test_marketplace_public_routes_use_vendor_id_not_listing_row_id(session: AsyncSession):
    await session.execute(delete(ReviewModel))
    await session.execute(delete(VendorListingModel))
    await session.commit()
    listing_uuid = uuid.uuid4()
    vendor_uuid = uuid.uuid4()
    session.add(
        VendorListingModel(
            id=listing_uuid,
            vendor_id=vendor_uuid,
            business_name="Routed Vendor",
            category="photography",
            description="Visible listing",
            service_area="Kigali",
            approval_status="approved",
            is_verified=True,
        )
    )
    await session.commit()

    async def override_session():
        yield session

    app.dependency_overrides[get_session] = override_session
    transport = ASGITransport(app=app)
    try:
        async with AsyncClient(transport=transport, base_url="http://test") as client:
            search_response = await client.get("/api/v1/marketplace/search?page=1&page_size=12")
            vendor_response = await client.get(f"/api/v1/marketplace/vendors/{vendor_uuid}")
            listing_response = await client.get(f"/api/v1/marketplace/vendors/{listing_uuid}")
            reviews_response = await client.get(f"/api/v1/marketplace/vendors/{vendor_uuid}/reviews")
    finally:
        app.dependency_overrides.clear()

    assert search_response.status_code == 200
    assert search_response.json()["items"][0]["id"] == str(vendor_uuid)
    assert search_response.json()["items"][0]["id"] != str(listing_uuid)
    assert vendor_response.status_code == 200
    assert vendor_response.json()["id"] == str(vendor_uuid)
    assert listing_response.status_code == 404
    assert reviews_response.status_code == 200
    assert reviews_response.json() == []


@pytest.mark.asyncio
async def test_search_filters_approved_only_and_partial_location(session: AsyncSession):
    await session.execute(delete(VendorListingModel))
    await session.commit()

    session.add_all(
        [
            VendorListingModel(
                vendor_id=uuid.uuid4(),
                business_name="Kigali Photo",
                category="photography",
                description="Visible listing",
                service_area="Kigali, Rwanda",
                approval_status="approved",
            ),
            VendorListingModel(
                vendor_id=uuid.uuid4(),
                business_name="Hidden Kigali Photo",
                category="photography",
                description="Hidden listing",
                service_area="Kigali, Rwanda",
                approval_status="rejected",
            ),
            VendorListingModel(
                vendor_id=uuid.uuid4(),
                business_name="Musanze Photo",
                category="photography",
                description="Other city listing",
                service_area="Musanze, Rwanda",
                approval_status="approved",
            ),
        ]
    )
    await session.commit()

    service = MarketplaceSearchService(session=session, cache=None)

    result = await service.search(
        MarketplaceSearchCriteria(category="photography", location="Kigali"),
        client_id="test-client",
    )

    assert result.total == 1
    assert result.items[0].business_name == "Kigali Photo"


@pytest.mark.asyncio
async def test_redis_unavailable_does_not_make_search_fail(session: AsyncSession):
    await session.execute(delete(VendorListingModel))
    await session.commit()
    session.add(
        VendorListingModel(
            vendor_id=uuid.uuid4(),
            business_name="No Redis Vendor",
            category="photography",
            description="Visible listing",
            service_area="Kigali",
            approval_status="approved",
        )
    )
    await session.commit()

    class BrokenRedis:
        async def incr(self, *args, **kwargs):
            raise RedisError("redis unavailable")

    cache = MarketplaceSearchCache(
        redis_client=BrokenRedis(),
        ttl_seconds=60,
        rate_limit_requests=10,
        rate_limit_window_seconds=60,
    )
    service = MarketplaceSearchService(session=session, cache=cache)

    result = await service.search(MarketplaceSearchCriteria(page=1), client_id="test-client")

    assert result.total == 1
    assert result.items[0].business_name == "No Redis Vendor"


def test_get_cors_origins_includes_custom_domain(monkeypatch):
    monkeypatch.delenv("FASTAPI_CORS_ORIGINS", raising=False)
    monkeypatch.setenv("FASTAPI_ENV", "development")

    origins = get_cors_origins()

    assert "https://www.linkapro.rw" in origins
    assert "https://linkapro.rw" in origins
    assert "https://linkapro.vercel.app" in origins


def test_production_cors_requires_custom_domains(monkeypatch):
    monkeypatch.setenv("FASTAPI_ENV", "production")
    monkeypatch.setenv("FASTAPI_CORS_ORIGINS", "https://linkapro.vercel.app")

    with pytest.raises(RuntimeError, match="https://www.linkapro.rw"):
        get_cors_origins()


def test_rediss_cert_required_is_normalized():
    url = normalize_redis_url("rediss://default:secret@example.redis:6379?ssl_cert_reqs=CERT_REQUIRED")

    assert "ssl_cert_reqs=required" in url
    assert "CERT_REQUIRED" not in url


def test_database_url_normalization_requires_asyncpg():
    assert normalize_database_url("postgresql://u:p@example.com/db").startswith("postgresql+asyncpg://")
    with pytest.raises(RuntimeError, match="FASTAPI_DATABASE_URL must use postgresql\\+asyncpg://"):
        normalize_database_url("mysql://u:p@example.com/db")


@pytest.mark.asyncio
async def test_internal_upsert_is_idempotent_and_non_approved_payload_deletes(session: AsyncSession, monkeypatch):
    await session.execute(delete(VendorListingModel))
    await session.commit()

    class FakeCache:
        def __init__(self):
            self.invalidations = 0

        async def invalidate(self):
            self.invalidations += 1

    cache = FakeCache()
    monkeypatch.setattr("fastapi_app.routers.internal.INTERNAL_SHARED_SECRET", "test-secret")
    monkeypatch.setattr("fastapi_app.routers.internal.get_marketplace_search_cache", lambda: cache)
    monkeypatch.setenv("FASTAPI_ENV", "development")
    monkeypatch.setenv("FASTAPI_ALLOW_LEGACY_INTERNAL_SECRET", "true")

    async def override_session():
        yield session

    vendor_id = uuid.uuid4()
    app.dependency_overrides[get_session] = override_session
    transport = ASGITransport(app=app)
    try:
        async with AsyncClient(transport=transport, base_url="http://test") as client:
            first = await client.post(
                "/internal/listings",
                headers={"X-Internal-Secret": "test-secret"},
                json={
                    "vendor_id": str(vendor_id),
                    "business_name": "Original",
                    "category": "photography",
                    "description": "Visible listing",
                    "service_area": "Kigali",
                    "approval_status": "approved",
                },
            )
            second = await client.post(
                "/internal/listings",
                headers={"X-Internal-Secret": "test-secret"},
                json={
                    "vendor_id": str(vendor_id),
                    "business_name": "Updated",
                    "category": "photography",
                    "description": "Updated listing",
                    "service_area": "Kigali, Rwanda",
                    "approval_status": "approved",
                },
            )
    finally:
        app.dependency_overrides.clear()

    assert first.status_code == 200
    assert second.status_code == 200
    count = await session.scalar(select(func.count()).select_from(VendorListingModel))
    listing = await session.scalar(select(VendorListingModel).where(VendorListingModel.vendor_id == vendor_id))
    assert count == 1
    assert listing.business_name == "Updated"

    app.dependency_overrides[get_session] = override_session
    transport = ASGITransport(app=app)
    try:
        async with AsyncClient(transport=transport, base_url="http://test") as client:
            deleted = await client.post(
                "/internal/listings",
                headers={"X-Internal-Secret": "test-secret"},
                json={
                    "vendor_id": str(vendor_id),
                    "business_name": "Updated",
                    "category": "photography",
                    "description": "Updated listing",
                    "service_area": "Kigali, Rwanda",
                    "approval_status": "rejected",
                },
            )
    finally:
        app.dependency_overrides.clear()

    assert deleted.status_code == 200
    assert deleted.json()["listed"] is False
    count_after_delete = await session.scalar(select(func.count()).select_from(VendorListingModel))
    assert count_after_delete == 0
    assert cache.invalidations == 3
