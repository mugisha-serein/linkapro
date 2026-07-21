import os
from pathlib import Path
from typing import AsyncGenerator

from dotenv import load_dotenv
from sqlalchemy.ext.asyncio import (
    AsyncSession,
    create_async_engine,
    async_sessionmaker,
)
from sqlalchemy.orm import declarative_base
from fastapi_app.config import get_database_engine_options, normalize_database_url

BASE_DIR = Path(__file__).resolve().parents[1]
load_dotenv(BASE_DIR / ".env")

DATABASE_URL = os.getenv("FASTAPI_DATABASE_URL")

if not DATABASE_URL:
    raise RuntimeError("FASTAPI_DATABASE_URL is missing.")

DATABASE_URL = normalize_database_url(DATABASE_URL)

engine = create_async_engine(
    DATABASE_URL,
    **get_database_engine_options(DATABASE_URL),
)

AsyncSessionLocal = async_sessionmaker(
    engine,
    class_=AsyncSession,
    expire_on_commit=False,
)

Base = declarative_base()


async def get_session() -> AsyncGenerator[AsyncSession, None]:
    async with AsyncSessionLocal() as session:
        yield session
