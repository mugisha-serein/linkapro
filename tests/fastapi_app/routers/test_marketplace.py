import uuid
import pytest
from datetime import datetime, timezone
from httpx import AsyncClient, ASGITransport
from unittest.mock import AsyncMock, Mock
from sqlalchemy.exc import SQLAlchemyError

from fastapi_app.main import app
from fastapi_app.dependencies import get_query_handlers, get_command_handlers, get_marketplace_search_service
from application.marketplace.dtos import SearchResultDTO, VendorListingDTO


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
    assert response.json()["detail"] == "Marketplace search is temporarily unavailable."


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
