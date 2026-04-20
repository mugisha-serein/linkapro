import asyncio
import pytest
from sqlalchemy.ext.asyncio import create_async_engine, AsyncSession
from sqlalchemy.orm import sessionmaker
from sqlalchemy import text

# Ensure models are imported and attached to Base.metadata BEFORE engine fixture runs
from fastapi_app.database import Base
from fastapi_app.marketplace.models import VendorListingModel, ReviewModel

@pytest.fixture(scope="session")
def event_loop():
    loop = asyncio.get_event_loop_policy().new_event_loop()
    yield loop
    loop.close()

@pytest.fixture(scope="session")
async def engine():
    DATABASE_URL = "sqlite+aiosqlite:///:memory:"
    engine = create_async_engine(DATABASE_URL, echo=False)

    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.create_all)
        if "postgresql" in DATABASE_URL:
            await conn.execute(text("CREATE EXTENSION IF NOT EXISTS pg_trgm"))
    
    yield engine
    await engine.dispose()

@pytest.fixture
async def session(engine):
    async_session = sessionmaker(engine, class_=AsyncSession, expire_on_commit=False)
    async with async_session() as session:
        yield session
        await session.rollback()

@pytest.mark.asyncio
async def test_tables_exist(session):
    from sqlalchemy import inspect
    def get_tables(conn):
        inspector = inspect(conn)
        return inspector.get_table_names()
    tables = await session.run_sync(get_tables)
    assert "marketplace_vendorlisting" in tables
    assert "marketplace_review" in tables   