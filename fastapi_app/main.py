import logging
import uuid

from fastapi import FastAPI, Request
from fastapi.middleware.cors import CORSMiddleware
from fastapi.middleware.gzip import GZipMiddleware
from fastapi.middleware.trustedhost import TrustedHostMiddleware
from fastapi.responses import JSONResponse
from sqlalchemy import text
from sqlalchemy.exc import SQLAlchemyError

from fastapi_app.config import get_bool, get_cors_origins, get_fastapi_env, get_trusted_hosts, is_production
from fastapi_app.database import Base, engine
from fastapi_app.migrations.marketplace_search import apply_marketplace_search_schema
from fastapi_app.routers import internal, marketplace

logger = logging.getLogger(__name__)
app = FastAPI(title="Event Planning Marketplace API", version="1.0")

app.add_middleware(GZipMiddleware, minimum_size=1024)
app.add_middleware(TrustedHostMiddleware, allowed_hosts=get_trusted_hosts())
app.add_middleware(
    CORSMiddleware,
    allow_origins=get_cors_origins(),
    allow_credentials=True,
    allow_methods=["GET", "POST", "DELETE", "OPTIONS"],
    allow_headers=["*"],
    expose_headers=["X-Request-ID"],
)

app.include_router(marketplace.router, prefix="/api/v1/marketplace")
app.include_router(internal.router)


@app.middleware("http")
async def add_request_context_and_security_headers(request: Request, call_next):
    request_id = request.headers.get("x-request-id") or str(uuid.uuid4())
    request.state.request_id = request_id
    response = await call_next(request)
    response.headers["X-Request-ID"] = request_id
    response.headers.setdefault("X-Content-Type-Options", "nosniff")
    response.headers.setdefault("X-Frame-Options", "DENY")
    response.headers.setdefault("Referrer-Policy", "strict-origin-when-cross-origin")
    response.headers.setdefault("Permissions-Policy", "geolocation=(), microphone=(), camera=()")
    if is_production():
        response.headers.setdefault("Strict-Transport-Security", "max-age=31536000; includeSubDomains")
    return response


@app.exception_handler(SQLAlchemyError)
async def sqlalchemy_exception_handler(request: Request, exc: SQLAlchemyError):
    request_id = _get_request_id(request)
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
    request_id = _get_request_id(request)
    logger.exception("Unexpected FastAPI request error.", extra={"request_id": request_id, "path": request.url.path})
    return JSONResponse(
        status_code=500,
        content={
            "detail": "Unexpected server error.",
            "request_id": request_id,
        },
    )


def should_bootstrap_schema() -> bool:
    return get_fastapi_env() == "development" and get_bool("FASTAPI_SCHEMA_BOOTSTRAP", default=False)


@app.get("/live", include_in_schema=False)
async def liveness_probe():
    return {"status": "ok", "service": "marketplace-fastapi"}


@app.get("/ready", include_in_schema=False)
async def readiness_probe():
    await verify_marketplace_schema_ready()
    return {"status": "ok", "database": "ready", "service": "marketplace-fastapi"}


@app.on_event("startup")
async def ensure_database_schema():
    if should_bootstrap_schema():
        async with engine.begin() as conn:
            await conn.run_sync(Base.metadata.create_all)
            await apply_marketplace_search_schema(conn)
        return

    await verify_marketplace_schema_ready()


async def verify_marketplace_schema_ready() -> None:
    async with engine.begin() as conn:
        if engine.dialect.name == "postgresql":
            result = await conn.execute(text("SELECT to_regclass('public.marketplace_vendorlisting')"))
            exists = result.scalar_one() is not None
        else:
            result = await conn.execute(
                text("SELECT name FROM sqlite_master WHERE type = 'table' AND name = 'marketplace_vendorlisting'")
            )
            exists = result.scalar_one_or_none() is not None

        if not exists:
            raise RuntimeError(
                "FastAPI marketplace schema is missing. Run the marketplace database "
                "migration/bootstrap step before starting FastAPI in production."
            )


def _get_request_id(request: Request) -> str:
    return getattr(request.state, "request_id", None) or request.headers.get("x-request-id") or str(uuid.uuid4())
