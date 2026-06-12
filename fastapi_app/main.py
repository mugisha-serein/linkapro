import os
import logging
import uuid

from fastapi import FastAPI, Request
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse
from sqlalchemy import text
from sqlalchemy.exc import SQLAlchemyError

from fastapi_app.config import get_cors_origins, require_bool
from fastapi_app.database import Base, engine
from fastapi_app.migrations.marketplace_search import apply_marketplace_search_schema
from fastapi_app.routers import internal, marketplace

logger = logging.getLogger(__name__)
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


@app.exception_handler(SQLAlchemyError)
async def sqlalchemy_exception_handler(request: Request, exc: SQLAlchemyError):
    request_id = str(uuid.uuid4())
    logger.exception("Database error in FastAPI request.", extra={"request_id": request_id, "path": request.url.path})
    return JSONResponse(
        status_code=503,
        content={
            "detail": "Marketplace service is temporarily unavailable.",
            "request_id": request_id,
        },
    )


@app.exception_handler(Exception)
async def unexpected_exception_handler(request: Request, exc: Exception):
    request_id = str(uuid.uuid4())
    logger.exception("Unexpected FastAPI request error.", extra={"request_id": request_id, "path": request.url.path})
    return JSONResponse(
        status_code=500,
        content={
            "detail": "Unexpected server error.",
            "request_id": request_id,
        },
    )


def should_bootstrap_schema() -> bool:
    return os.getenv("FASTAPI_ENV") == "development" and require_bool("FASTAPI_SCHEMA_BOOTSTRAP")


@app.on_event("startup")
async def ensure_database_schema():
    async with engine.begin() as conn:
        if should_bootstrap_schema():
            await conn.run_sync(Base.metadata.create_all)
            await apply_marketplace_search_schema(conn)
            return

        result = await conn.execute(text("SELECT to_regclass('public.marketplace_vendorlisting')"))
        if result.scalar_one() is None:
            raise RuntimeError(
                "FastAPI marketplace schema is missing. Run the marketplace database "
                "migration/bootstrap step before starting FastAPI in production."
            )
