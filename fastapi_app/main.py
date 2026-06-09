import os

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from fastapi_app.config import get_cors_origins, require_bool
from fastapi_app.database import Base, engine
from fastapi_app.migrations.marketplace_search import apply_marketplace_search_schema
from fastapi_app.routers import internal, marketplace

app = FastAPI(title="Event Planning Marketplace API", version="1.0")

app.add_middleware(
    CORSMiddleware,
    allow_origins=get_cors_origins(),
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

app.include_router(marketplace.router, prefix="/api/v1/marketplace")
app.include_router(internal.router)


def should_bootstrap_schema() -> bool:
    return os.getenv("FASTAPI_ENV") == "development" and require_bool("FASTAPI_SCHEMA_BOOTSTRAP")


@app.on_event("startup")
async def ensure_database_schema():
    if not should_bootstrap_schema():
        return

    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.create_all)
        await apply_marketplace_search_schema(conn)
