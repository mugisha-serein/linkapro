import uuid
import pytest
from datetime import datetime, timezone
from httpx import AsyncClient, ASGITransport
from unittest.mock import AsyncMock, Mock

from fastapi_app.main import app
from fastapi_app.dependencies import get_query_handlers, get_command_handlers
from application.marketplace.dtos import SearchResultDTO


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
async def test_post_review_success(test_app, mock_command_handlers):
    vendor_id = str(uuid.uuid4())
    author_id = str(uuid.uuid4())
    
    review_dto = Mock()
    review_dto.id = str(uuid.uuid4())
    review_dto.vendor_id = vendor_id
    review_dto.author_user_id = author_id
    review_dto.rating = 5
    review_dto.comment = "Nice"
    review_dto.created_at = datetime.now(timezone.utc)
    
    mock_command_handlers.post_review.return_value = review_dto

    transport = ASGITransport(app=test_app)
    async with AsyncClient(transport=transport, base_url="http://test") as client:
        response = await client.post(
            f"/api/v1/marketplace/vendors/{vendor_id}/reviews",
            json={"author_user_id": author_id, "rating": 5, "comment": "Nice"},
        )
    
    assert response.status_code == 201
    assert response.json()["rating"] == 5
