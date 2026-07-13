from datetime import datetime, timezone as dt_timezone
from types import SimpleNamespace
from unittest.mock import Mock
import uuid

from domain.vendors.entities import PortfolioImage
from infrastructure.repos.portfolio import django_repository as repo_module
from infrastructure.repos.portfolio.django_repository import DjangoPortfolioImageRepository


def _portfolio_model(image_id=None, vendor_id=None):
    now = datetime(2026, 1, 1, tzinfo=dt_timezone.utc)
    return SimpleNamespace(
        id=image_id or uuid.uuid4(),
        vendor_id=vendor_id or uuid.uuid4(),
        vendor=None,
        public_id="portfolio/image",
        secure_url="https://cdn.example.test/image.jpg",
        media_type="image",
        caption="Original caption",
        order=1,
        upload_status="uploaded",
        quality_status="passed",
        visibility_status="approved",
        upload_error=None,
        failure_reason=None,
        rejection_reason=None,
        original_filename="image.jpg",
        mime_type="image/jpeg",
        file_size=1024,
        local_preview_url=None,
        cloudinary_public_id="portfolio/image",
        cloudinary_secure_url="https://cdn.example.test/image.jpg",
        width=800,
        height=600,
        duration_seconds=None,
        analyzer_score=None,
        analyzer_summary=None,
        is_active=True,
        is_deleted=False,
        deleted_at=None,
        deleted_by_id=None,
        created_at=now,
        updated_at=now,
        save=Mock(),
    )


class _Manager:
    def __init__(self, obj):
        self.obj = obj
        self.calls = []

    def get(self, **kwargs):
        self.calls.append(kwargs)
        return self.obj


def test_save_uses_all_objects_so_soft_deleted_images_are_updated(monkeypatch):
    image_id = uuid.uuid4()
    vendor_id = uuid.uuid4()
    existing_model = _portfolio_model(image_id=image_id, vendor_id=vendor_id)
    existing_model.is_deleted = True
    all_objects = _Manager(existing_model)
    active_objects = _Manager(_portfolio_model())
    vendor_manager = _Manager(SimpleNamespace(id=vendor_id))

    monkeypatch.setattr(repo_module.DjangoImage, "all_objects", all_objects)
    monkeypatch.setattr(repo_module.DjangoImage, "objects", active_objects)
    monkeypatch.setattr(repo_module.DjangoVendor, "objects", vendor_manager)

    domain_image = PortfolioImage(
        id=image_id,
        vendor_id=vendor_id,
        public_id="portfolio/updated-image",
        secure_url="https://cdn.example.test/updated.jpg",
        caption="Updated caption",
        order=2,
        is_active=False,
        is_deleted=True,
    )

    saved = DjangoPortfolioImageRepository().save(domain_image)

    assert saved.id == image_id
    assert saved.public_id == "portfolio/updated-image"
    assert existing_model.public_id == "portfolio/updated-image"
    assert existing_model.is_deleted is True
    assert all_objects.calls == [{"id": image_id}]
    assert active_objects.calls == []
    existing_model.save.assert_called_once_with()


def test_delete_marks_portfolio_image_inactive_deleted_and_records_deleter(monkeypatch):
    image_id = uuid.uuid4()
    deleted_by_id = uuid.uuid4()
    deleted_at = datetime(2026, 1, 2, tzinfo=dt_timezone.utc)
    model = _portfolio_model(image_id=image_id)
    all_objects = _Manager(model)

    monkeypatch.setattr(repo_module.DjangoImage, "all_objects", all_objects)
    monkeypatch.setattr(repo_module.timezone, "now", lambda: deleted_at)

    DjangoPortfolioImageRepository().delete(image_id, deleted_by_id=deleted_by_id)

    assert model.is_active is False
    assert model.is_deleted is True
    assert model.deleted_at == deleted_at
    assert model.deleted_by_id == deleted_by_id
    assert all_objects.calls == [{"id": image_id}]
    model.save.assert_called_once_with(
        update_fields=["is_active", "is_deleted", "deleted_at", "deleted_by", "updated_at"]
    )
