from __future__ import annotations

from dataclasses import MISSING, fields
import uuid

import pytest

from application.vendors.portfolio.dtos import PortfolioImageDTO
from application.vendors.shared.handlers import VendorCommandHandlers
from domain.vendors.portfolio.entity import PortfolioImage


def _required_dto_values() -> dict:
    return {
        "id": uuid.uuid4(),
        "vendor_id": uuid.uuid4(),
        "secure_url": "https://example.com/portfolio.jpg",
        "caption": "Reception setup",
        "order": 2,
        "media_type": "image",
        "upload_status": "uploaded",
        "quality_status": "passed",
        "visibility_status": "approved",
        "is_active": True,
    }


def test_portfolio_image_dto_version_has_no_default_and_is_required():
    dto_fields = {field.name: field for field in fields(PortfolioImageDTO)}

    assert dto_fields["version"].default is MISSING
    assert dto_fields["version"].default_factory is MISSING

    with pytest.raises(TypeError, match="version"):
        PortfolioImageDTO(**_required_dto_values())


def test_portfolio_image_dto_keeps_all_other_existing_defaults():
    dto = PortfolioImageDTO(**_required_dto_values(), version=7)

    assert dto.upload_error is None
    assert dto.failure_reason is None
    assert dto.rejection_reason is None
    assert dto.original_filename is None
    assert dto.mime_type == ""
    assert dto.file_size == 0
    assert dto.local_preview_url is None
    assert dto.cloudinary_public_id is None
    assert dto.cloudinary_secure_url is None
    assert dto.width is None
    assert dto.height is None
    assert dto.duration_seconds is None
    assert dto.analyzer_score is None
    assert dto.analyzer_summary is None
    assert dto.is_deleted is False
    assert dto.deleted_at is None


def test_portfolio_image_application_mapping_provides_exact_resource_version():
    image = PortfolioImage(
        id=uuid.uuid4(),
        vendor_id=uuid.uuid4(),
        public_id="portfolio-asset",
        secure_url="https://example.com/portfolio.jpg",
        caption="Reception setup",
        order=2,
        version=11,
    )

    dto = VendorCommandHandlers._to_image_dto(image)

    assert isinstance(dto, PortfolioImageDTO)
    assert dto.id == image.id
    assert dto.version == 11
    assert dto.version == image.version
