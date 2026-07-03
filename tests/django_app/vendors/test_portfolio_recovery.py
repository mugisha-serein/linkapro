from io import StringIO

import pytest
from django.core.files.base import ContentFile
from django.core.files.storage import default_storage
from django.core.management import call_command

from django_app.vendors.models import PortfolioImage
from django_app.vendors.portfolio_recovery import (
    HAS_CLOUDINARY_PUBLIC_ID_MISSING_URL,
    HAS_CLOUDINARY_URL_NEEDS_PROCESSING,
    HAS_TEMP_FILE_CAN_UPLOAD,
    MISSING_SOURCE_UNRECOVERABLE,
    UNRECOVERABLE_MESSAGE,
    recover_stuck_portfolio_media,
)
from tests.factories import create_vendor_profile


@pytest.mark.django_db
def test_recovery_dry_run_classifies_without_mutating_or_queueing(monkeypatch):
    vendor = create_vendor_profile()
    complete = PortfolioImage.objects.create(
        vendor=vendor,
        public_id="portfolio/complete",
        secure_url="https://res.cloudinary.com/demo/complete.jpg",
        cloudinary_public_id="portfolio/complete",
        cloudinary_secure_url="https://res.cloudinary.com/demo/complete.jpg",
        upload_status=PortfolioImage.UploadStatus.UPLOADED,
        quality_status=PortfolioImage.QualityStatus.PASSED,
    )
    needs_processing = PortfolioImage.objects.create(
        vendor=vendor,
        cloudinary_secure_url="https://res.cloudinary.com/demo/queued.jpg",
        upload_status=PortfolioImage.UploadStatus.QUEUED,
        quality_status=PortfolioImage.QualityStatus.PENDING_ANALYSIS,
    )
    missing_url = PortfolioImage.objects.create(
        vendor=vendor,
        cloudinary_public_id="portfolio/missing-url",
        secure_url="",
        cloudinary_secure_url=None,
        upload_status=PortfolioImage.UploadStatus.FAILED,
        quality_status=PortfolioImage.QualityStatus.PENDING_ANALYSIS,
    )
    temp_path = default_storage.save("vendor_portfolio_uploads/recovery/temp.jpg", ContentFile(b"image"))
    temp_backed = PortfolioImage.objects.create(
        vendor=vendor,
        temp_upload_path=temp_path,
        upload_status=PortfolioImage.UploadStatus.PROCESSING_DEFERRED,
        quality_status=PortfolioImage.QualityStatus.PENDING_ANALYSIS,
    )
    no_source = PortfolioImage.objects.create(
        vendor=vendor,
        upload_status=PortfolioImage.UploadStatus.FAILED,
        quality_status=PortfolioImage.QualityStatus.PENDING_ANALYSIS,
    )

    monkeypatch.setattr(
        "django_app.vendors.portfolio_recovery.process_vendor_portfolio_media_task.delay",
        lambda *_args, **_kwargs: (_ for _ in ()).throw(AssertionError("dry run should not queue")),
    )

    summary = recover_stuck_portfolio_media(dry_run=True)

    assert summary["scanned"] == 5
    assert summary["categories"]["already_complete"] == 1
    assert summary["categories"][HAS_CLOUDINARY_URL_NEEDS_PROCESSING] == 1
    assert summary["categories"][HAS_CLOUDINARY_PUBLIC_ID_MISSING_URL] == 1
    assert summary["categories"][HAS_TEMP_FILE_CAN_UPLOAD] == 1
    assert summary["categories"][MISSING_SOURCE_UNRECOVERABLE] == 1
    assert summary["updated"] == 0
    assert summary["queued"] == 0
    assert PortfolioImage.objects.get(id=complete.id).upload_status == PortfolioImage.UploadStatus.UPLOADED
    assert PortfolioImage.objects.get(id=needs_processing.id).upload_status == PortfolioImage.UploadStatus.QUEUED
    assert PortfolioImage.objects.get(id=missing_url.id).cloudinary_secure_url is None
    assert PortfolioImage.objects.get(id=temp_backed.id).temp_upload_path == temp_path
    assert PortfolioImage.objects.get(id=no_source.id).upload_error is None


@pytest.mark.django_db
def test_recovery_requeues_existing_cloudinary_url(monkeypatch):
    vendor = create_vendor_profile()
    image = PortfolioImage.objects.create(
        vendor=vendor,
        cloudinary_secure_url="https://res.cloudinary.com/demo/queued.jpg",
        upload_status=PortfolioImage.UploadStatus.FAILED,
        quality_status=PortfolioImage.QualityStatus.FAILED,
        visibility_status=PortfolioImage.VisibilityStatus.APPROVED,
        upload_error="old error",
        failure_reason="old error",
    )
    queued = []
    monkeypatch.setattr(
        "django_app.vendors.portfolio_recovery.process_vendor_portfolio_media_task.delay",
        queued.append,
    )

    summary = recover_stuck_portfolio_media(dry_run=False)

    image.refresh_from_db()
    assert summary["categories"][HAS_CLOUDINARY_URL_NEEDS_PROCESSING] == 1
    assert summary["queued"] == 1
    assert queued == [str(image.id)]
    assert image.upload_status == PortfolioImage.UploadStatus.QUEUED
    assert image.quality_status == PortfolioImage.QualityStatus.PENDING_ANALYSIS
    assert image.visibility_status == PortfolioImage.VisibilityStatus.PRIVATE
    assert image.upload_error is None
    assert image.failure_reason is None
    assert image.secure_url == "https://res.cloudinary.com/demo/queued.jpg"


@pytest.mark.django_db
def test_recovery_restores_secure_url_from_cloudinary_public_id(monkeypatch):
    vendor = create_vendor_profile()
    image = PortfolioImage.objects.create(
        vendor=vendor,
        cloudinary_public_id="portfolio/missing-url",
        upload_status=PortfolioImage.UploadStatus.FAILED,
        quality_status=PortfolioImage.QualityStatus.PENDING_ANALYSIS,
    )
    monkeypatch.setattr(
        "django_app.vendors.portfolio_recovery.CloudinaryAdapter.get_resource",
        lambda self, public_id, resource_type="image": {
            "public_id": public_id,
            "secure_url": "https://res.cloudinary.com/demo/restored.jpg",
            "width": 1200,
            "height": 800,
        },
    )
    queued = []
    monkeypatch.setattr(
        "django_app.vendors.portfolio_recovery.process_vendor_portfolio_media_task.delay",
        queued.append,
    )

    summary = recover_stuck_portfolio_media(dry_run=False)

    image.refresh_from_db()
    assert summary["categories"][HAS_CLOUDINARY_PUBLIC_ID_MISSING_URL] == 1
    assert queued == [str(image.id)]
    assert image.secure_url == "https://res.cloudinary.com/demo/restored.jpg"
    assert image.cloudinary_secure_url == "https://res.cloudinary.com/demo/restored.jpg"
    assert image.public_id == "portfolio/missing-url"
    assert image.width == 1200
    assert image.height == 800
    assert image.upload_status == PortfolioImage.UploadStatus.QUEUED


@pytest.mark.django_db
def test_recovery_uploads_existing_temp_file_to_cloudinary(monkeypatch):
    vendor = create_vendor_profile()
    temp_path = default_storage.save("vendor_portfolio_uploads/recovery/upload.jpg", ContentFile(b"image"))
    image = PortfolioImage.objects.create(
        vendor=vendor,
        temp_upload_path=temp_path,
        upload_status=PortfolioImage.UploadStatus.PROCESSING_DEFERRED,
        quality_status=PortfolioImage.QualityStatus.PENDING_ANALYSIS,
        local_preview_url="/media/vendor_portfolio_uploads/recovery/upload.jpg",
    )
    monkeypatch.setattr(
        "django_app.vendors.portfolio_recovery.CloudinaryAdapter.upload_image",
        lambda self, file, fallback_to_storage=False: {
            "public_id": "vendor_portfolio/recovered",
            "secure_url": "https://res.cloudinary.com/demo/recovered.jpg",
        },
    )
    queued = []
    monkeypatch.setattr(
        "django_app.vendors.portfolio_recovery.process_vendor_portfolio_media_task.delay",
        queued.append,
    )

    summary = recover_stuck_portfolio_media(dry_run=False)

    image.refresh_from_db()
    assert summary["categories"][HAS_TEMP_FILE_CAN_UPLOAD] == 1
    assert queued == [str(image.id)]
    assert image.public_id == "vendor_portfolio/recovered"
    assert image.cloudinary_secure_url == "https://res.cloudinary.com/demo/recovered.jpg"
    assert image.temp_upload_path is None
    assert image.local_preview_url is None
    assert not default_storage.exists(temp_path)


@pytest.mark.django_db
def test_recovery_upload_failure_leaves_temp_backed_row_retriable(monkeypatch):
    vendor = create_vendor_profile()
    temp_path = default_storage.save("vendor_portfolio_uploads/recovery/retry.jpg", ContentFile(b"image"))
    image = PortfolioImage.objects.create(
        vendor=vendor,
        temp_upload_path=temp_path,
        upload_status=PortfolioImage.UploadStatus.PROCESSING_DEFERRED,
        quality_status=PortfolioImage.QualityStatus.PENDING_ANALYSIS,
        local_preview_url="/media/vendor_portfolio_uploads/recovery/retry.jpg",
    )
    monkeypatch.setattr(
        "django_app.vendors.portfolio_recovery.CloudinaryAdapter.upload_image",
        lambda self, file, fallback_to_storage=False: (_ for _ in ()).throw(RuntimeError("cloudinary unavailable")),
    )

    summary = recover_stuck_portfolio_media(dry_run=False)

    image.refresh_from_db()
    assert summary["categories"][HAS_TEMP_FILE_CAN_UPLOAD] == 1
    assert summary["updated"] == 0
    assert summary["unrecoverable"] == 0
    assert image.upload_status == PortfolioImage.UploadStatus.PROCESSING_DEFERRED
    assert image.temp_upload_path == temp_path
    assert default_storage.exists(temp_path)


@pytest.mark.django_db
def test_recovery_public_id_lookup_failure_does_not_mark_unrecoverable(monkeypatch):
    vendor = create_vendor_profile()
    image = PortfolioImage.objects.create(
        vendor=vendor,
        cloudinary_public_id="portfolio/missing-url",
        upload_status=PortfolioImage.UploadStatus.FAILED,
        quality_status=PortfolioImage.QualityStatus.PENDING_ANALYSIS,
    )
    monkeypatch.setattr(
        "django_app.vendors.portfolio_recovery.CloudinaryAdapter.get_resource",
        lambda self, public_id, resource_type="image": (_ for _ in ()).throw(RuntimeError("cloudinary unavailable")),
    )

    summary = recover_stuck_portfolio_media(dry_run=False)

    image.refresh_from_db()
    assert summary["categories"][HAS_CLOUDINARY_PUBLIC_ID_MISSING_URL] == 1
    assert summary["updated"] == 0
    assert summary["unrecoverable"] == 0
    assert image.upload_status == PortfolioImage.UploadStatus.FAILED
    assert image.upload_error is None


@pytest.mark.django_db
def test_recovery_marks_missing_source_unrecoverable_without_deleting():
    vendor = create_vendor_profile()
    image = PortfolioImage.objects.create(
        vendor=vendor,
        upload_status=PortfolioImage.UploadStatus.PROCESSING_DEFERRED,
        quality_status=PortfolioImage.QualityStatus.PENDING_ANALYSIS,
        visibility_status=PortfolioImage.VisibilityStatus.WAITING_APPROVAL,
    )

    summary = recover_stuck_portfolio_media(dry_run=False)

    image.refresh_from_db()
    assert summary["categories"][MISSING_SOURCE_UNRECOVERABLE] == 1
    assert image.upload_status == PortfolioImage.UploadStatus.FAILED
    assert image.visibility_status == PortfolioImage.VisibilityStatus.PRIVATE
    assert image.upload_error == UNRECOVERABLE_MESSAGE
    assert image.failure_reason == UNRECOVERABLE_MESSAGE
    assert PortfolioImage.objects.filter(id=image.id).exists()


@pytest.mark.django_db
def test_recover_portfolio_uploads_command_reports_categories():
    vendor = create_vendor_profile()
    PortfolioImage.objects.create(
        vendor=vendor,
        cloudinary_secure_url="https://res.cloudinary.com/demo/queued.jpg",
        upload_status=PortfolioImage.UploadStatus.QUEUED,
        quality_status=PortfolioImage.QualityStatus.PENDING_ANALYSIS,
    )
    output = StringIO()

    call_command("recover_portfolio_uploads", "--dry-run", stdout=output)

    assert "Dry run: true" in output.getvalue()
    assert f"{HAS_CLOUDINARY_URL_NEEDS_PROCESSING}: 1" in output.getvalue()
