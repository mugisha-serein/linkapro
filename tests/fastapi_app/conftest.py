import asyncio
import os
import pytest
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
async def engine():
    """Create a file-based SQLite engine and create all tables."""
    # File-based SQLite ensures tables persist across connections
    DATABASE_URL = "sqlite+aiosqlite:///./test_marketplace.db"
    engine = create_async_engine(DATABASE_URL, echo=False)

    async with engine.begin() as conn:
        # Drop all tables first (clean slate)
        await conn.run_sync(Base.metadata.drop_all)
        # Create all tables
        await conn.run_sync(Base.metadata.create_all)

    yield engine

    await engine.dispose()
    # Clean up the test database file
    if os.path.exists("./test_marketplace.db"):
        os.remove("./test_marketplace.db")

@pytest.fixture
async def session(engine):
    """Provide a transactional session for a test."""
    async_session = sessionmaker(engine, class_=AsyncSession, expire_on_commit=False)
    async with async_session() as session:
        yield session
        await session.rollback()