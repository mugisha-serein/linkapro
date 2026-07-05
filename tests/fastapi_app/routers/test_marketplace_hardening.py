import pytest
from httpx import ASGITransport, AsyncClient
from starlette.requests import Request

from fastapi_app.config import get_database_engine_options, get_trusted_hosts
from fastapi_app.dependencies import get_marketplace_client_identifier
from fastapi_app.main import app


@pytest.mark.asyncio
async def test_liveness_probe_adds_request_id_and_security_headers():
    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://test") as client:
        response = await client.get("/live", headers={"X-Request-ID": "test-request-id"})

    assert response.status_code == 200
    assert response.json() == {"status": "ok", "service": "marketplace-fastapi"}
    assert response.headers["x-request-id"] == "test-request-id"
    assert response.headers["x-content-type-options"] == "nosniff"
    assert response.headers["x-frame-options"] == "DENY"
    assert response.headers["referrer-policy"] == "strict-origin-when-cross-origin"


def test_production_trusted_hosts_rejects_wildcard(monkeypatch):
    monkeypatch.setenv("FASTAPI_ENV", "production")
    monkeypatch.setenv("FASTAPI_TRUSTED_HOSTS", "*")

    with pytest.raises(RuntimeError, match="FASTAPI_TRUSTED_HOSTS must not contain"):
        get_trusted_hosts()


def test_development_trusted_hosts_allows_test_clients(monkeypatch):
    monkeypatch.setenv("FASTAPI_ENV", "development")
    monkeypatch.delenv("FASTAPI_TRUSTED_HOSTS", raising=False)

    assert get_trusted_hosts() == ["*"]


def test_database_engine_options_apply_postgres_pool_hardening(monkeypatch):
    monkeypatch.delenv("FASTAPI_SQL_ECHO", raising=False)
    monkeypatch.delenv("FASTAPI_DB_POOL_RECYCLE_SECONDS", raising=False)
    monkeypatch.delenv("FASTAPI_DB_POOL_SIZE", raising=False)
    monkeypatch.delenv("FASTAPI_DB_MAX_OVERFLOW", raising=False)
    monkeypatch.delenv("FASTAPI_DB_POOL_TIMEOUT_SECONDS", raising=False)

    options = get_database_engine_options("postgresql+asyncpg://user:password@example.com/linkapro")

    assert options["pool_pre_ping"] is True
    assert options["pool_recycle"] == 1800
    assert options["pool_size"] == 5
    assert options["max_overflow"] == 5
    assert options["pool_timeout"] == 10


def test_marketplace_client_identifier_hashes_forwarded_client(monkeypatch):
    monkeypatch.setenv("FASTAPI_ENV", "production")
    monkeypatch.setenv("FASTAPI_TRUST_PROXY_HEADERS", "true")
    scope = {
        "type": "http",
        "method": "GET",
        "path": "/api/v1/marketplace/search",
        "headers": [(b"x-forwarded-for", b"203.0.113.10, 10.0.0.1")],
        "client": ("10.0.0.1", 12345),
        "server": ("test", 80),
        "scheme": "http",
        "query_string": b"",
    }

    identifier = get_marketplace_client_identifier(Request(scope))

    assert identifier.startswith("client:")
    assert "203.0.113.10" not in identifier
    assert len(identifier) == len("client:") + 32
