import asyncio
import os
import pytest
from sqlalchemy import text
from sqlalchemy.ext.asyncio import create_async_engine, AsyncSession
from sqlalchemy.orm import sessionmaker

# Import Base from your application (adjust path if needed)
from fastapi_app.database import Base

# Force import of all model modules so they register with Base.metadata
from fastapi_app.marketplace.models import VendorListingModel, ReviewModel  # noqa: F401

@pytest.fixture(scope="session")
def event_loop():
    """Create an instance of the default event loop for each test session."""
    loop = asyncio.get_event_loop_policy().new_event_loop()
    yield loop
    loop.close()

@pytest.fixture(scope="session")
def engine(event_loop):
    """Create a file-based SQLite engine and create all tables."""
    # File-based SQLite ensures tables persist across connections
    DATABASE_URL = "sqlite+aiosqlite:///./test_marketplace.db"
    engine = create_async_engine(DATABASE_URL, echo=False)

    async def setup():
        async with engine.begin() as conn:
            await conn.execute(text("DROP TABLE IF EXISTS marketplace_review"))
            await conn.execute(text("DROP TABLE IF EXISTS marketplace_vendorlisting"))
            await conn.execute(text(
                """
                CREATE TABLE marketplace_vendorlisting (
                    id UUID PRIMARY KEY,
                    vendor_id UUID NOT NULL UNIQUE,
                    external_id VARCHAR(128) UNIQUE,
                    business_name VARCHAR(200) NOT NULL,
                    category VARCHAR(50) NOT NULL,
                    description TEXT NOT NULL,
                    service_area VARCHAR(200) NOT NULL,
                    tags TEXT,
                    cover_image_url VARCHAR(500),
                    average_rating FLOAT,
                    total_reviews INTEGER,
                    is_verified BOOLEAN,
                    approval_status VARCHAR(20),
                    search_rank_score FLOAT,
                    search_vector TEXT,
                    created_at DATETIME DEFAULT CURRENT_TIMESTAMP,
                    updated_at DATETIME
                )
                """
            ))
            await conn.execute(text(
                """
                CREATE TABLE marketplace_review (
                    id UUID PRIMARY KEY,
                    vendor_id UUID NOT NULL,
                    author_user_id UUID NOT NULL,
                    rating INTEGER NOT NULL,
                    comment TEXT,
                    is_verified_purchase BOOLEAN,
                    created_at DATETIME DEFAULT CURRENT_TIMESTAMP,
                    FOREIGN KEY(vendor_id) REFERENCES marketplace_vendorlisting(vendor_id)
                )
                """
            ))

    event_loop.run_until_complete(setup())

    yield engine

    event_loop.run_until_complete(engine.dispose())
    # Clean up the test database file
    if os.path.exists("./test_marketplace.db"):
        os.remove("./test_marketplace.db")

@pytest.fixture
def session(engine, event_loop):
    """Provide a transactional session for a test."""
    async_session = sessionmaker(engine, class_=AsyncSession, expire_on_commit=False)
    session = async_session()
    yield session
    event_loop.run_until_complete(session.rollback())
    event_loop.run_until_complete(session.close())
