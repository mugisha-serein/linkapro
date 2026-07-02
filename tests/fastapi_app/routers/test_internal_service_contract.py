import json
import uuid

import pytest
from httpx import ASGITransport, AsyncClient
from sqlalchemy import delete, select
from sqlalchemy.ext.asyncio import AsyncSession

from fastapi_app.database import get_session
from fastapi_app.main import app
from fastapi_app.marketplace.models import VendorListingModel
from infrastructure.security.service_auth import build_service_headers, utc_timestamp


pytestmark = pytest.mark.asyncio


def signed_payload(method: str, path: str, payload: dict):
    body = json.dumps(payload, sort_keys=True, separators=(",", ":")).encode("utf-8")
    headers = {
        "Content-Type": "application/json",
        **build_service_headers(
            key="test-secret",
            method=method,
            path=path,
            payload=body,
            request_id=str(uuid.uuid4()),
            timestamp=utc_timestamp(),
        ),
    }
    return body, headers


async def install_session(session: AsyncSession):
    async def override_session():
        yield session

    app.dependency_overrides[get_session] = override_session


async def test_signed_internal_listing_request_is_accepted(session: AsyncSession, monkeypatch):
    await session.execute(delete(VendorListingModel))
    await session.commit()
    monkeypatch.setattr("fastapi_app.routers.internal.INTERNAL_SHARED_SECRET", "test-secret")
    await install_session(session)

    vendor_id = uuid.uuid4()
    body, headers = signed_payload(
        "POST",
        "/internal/listings",
        {
            "vendor_id": str(vendor_id),
            "business_name": "Signed Vendor",
            "category": "photography",
            "description": "Public approved marketplace listing.",
            "service_area": "Kigali",
            "approval_status": "approved",
            "is_verified": True,
        },
    )

    transport = ASGITransport(app=app)
    try:
        async with AsyncClient(transport=transport, base_url="http://test") as client:
            response = await client.post("/internal/listings", content=body, headers=headers)
    finally:
        app.dependency_overrides.clear()

    listing = await session.scalar(select(VendorListingModel).where(VendorListingModel.vendor_id == vendor_id))
    assert response.status_code == 200
    assert response.json() == {"status": "ok"}
    assert listing.business_name == "Signed Vendor"
    assert listing.approval_status == "approved"


async def test_legacy_internal_secret_rejected_by_default(session: AsyncSession, monkeypatch):
    monkeypatch.setattr("fastapi_app.routers.internal.INTERNAL_SHARED_SECRET", "test-secret")
    monkeypatch.setenv("FASTAPI_ENV", "development")
    monkeypatch.delenv("FASTAPI_ALLOW_LEGACY_INTERNAL_SECRET", raising=False)
    await install_session(session)

    transport = ASGITransport(app=app)
    try:
        async with AsyncClient(transport=transport, base_url="http://test") as client:
            response = await client.post(
                "/internal/listings",
                headers={"X-Internal-Secret": "test-secret"},
                json={
                    "vendor_id": str(uuid.uuid4()),
                    "business_name": "Legacy Vendor",
                    "category": "photography",
                    "description": "Public approved marketplace listing.",
                    "service_area": "Kigali",
                    "approval_status": "approved",
                },
            )
    finally:
        app.dependency_overrides.clear()

    assert response.status_code == 401


async def test_legacy_internal_secret_rejected_in_production_even_when_allowed(session: AsyncSession, monkeypatch):
    monkeypatch.setattr("fastapi_app.routers.internal.INTERNAL_SHARED_SECRET", "test-secret")
    monkeypatch.setenv("FASTAPI_ENV", "production")
    monkeypatch.setenv("FASTAPI_ALLOW_LEGACY_INTERNAL_SECRET", "true")
    await install_session(session)

    transport = ASGITransport(app=app)
    try:
        async with AsyncClient(transport=transport, base_url="http://test") as client:
            response = await client.post(
                "/internal/listings",
                headers={"X-Internal-Secret": "test-secret"},
                json={
                    "vendor_id": str(uuid.uuid4()),
                    "business_name": "Legacy Vendor",
                    "category": "photography",
                    "description": "Public approved marketplace listing.",
                    "service_area": "Kigali",
                    "approval_status": "approved",
                },
            )
    finally:
        app.dependency_overrides.clear()

    assert response.status_code == 401


async def test_legacy_internal_secret_allowed_only_with_non_production_opt_in(session: AsyncSession, monkeypatch):
    await session.execute(delete(VendorListingModel))
    await session.commit()
    monkeypatch.setattr("fastapi_app.routers.internal.INTERNAL_SHARED_SECRET", "test-secret")
    monkeypatch.setenv("FASTAPI_ENV", "development")
    monkeypatch.setenv("FASTAPI_ALLOW_LEGACY_INTERNAL_SECRET", "true")
    await install_session(session)

    vendor_id = uuid.uuid4()
    transport = ASGITransport(app=app)
    try:
        async with AsyncClient(transport=transport, base_url="http://test") as client:
            response = await client.post(
                "/internal/listings",
                headers={"X-Internal-Secret": "test-secret"},
                json={
                    "vendor_id": str(vendor_id),
                    "business_name": "Legacy Vendor",
                    "category": "photography",
                    "description": "Public approved marketplace listing.",
                    "service_area": "Kigali",
                    "approval_status": "approved",
                },
            )
    finally:
        app.dependency_overrides.clear()

    listing = await session.scalar(select(VendorListingModel).where(VendorListingModel.vendor_id == vendor_id))
    assert response.status_code == 200
    assert listing.business_name == "Legacy Vendor"


async def test_signed_internal_listing_request_validates_payload(session: AsyncSession, monkeypatch):
    monkeypatch.setattr("fastapi_app.routers.internal.INTERNAL_SHARED_SECRET", "test-secret")
    await install_session(session)

    body, headers = signed_payload(
        "POST",
        "/internal/listings",
        {
            "vendor_id": str(uuid.uuid4()),
            "business_name": "",
            "category": "photography",
            "description": "Public approved marketplace listing.",
            "service_area": "Kigali",
            "approval_status": "approved",
        },
    )

    transport = ASGITransport(app=app)
    try:
        async with AsyncClient(transport=transport, base_url="http://test") as client:
            response = await client.post("/internal/listings", content=body, headers=headers)
    finally:
        app.dependency_overrides.clear()

    assert response.status_code == 422
