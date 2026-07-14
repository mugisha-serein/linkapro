import pytest

from django_app.vendors.models import PortfolioImage
from tasks.image_tasks import process_vendor_portfolio_media_task
from tests.factories import create_vendor_profile


@pytest.mark.django_db
def test_portfolio_task_uses_remote_url_when_temp_path_is_stale(monkeypatch):
    vendor = create_vendor_profile()
    image = PortfolioImage.objects.create(
        vendor=vendor,
        public_id="vendor_portfolio/remote",
        secure_url="https://res.cloudinary.com/demo/remote.jpg",
        cloudinary_public_id="vendor_portfolio/remote",
        cloudinary_secure_url="https://res.cloudinary.com/demo/remote.jpg",
        temp_upload_path="vendor_portfolio_uploads/missing/remote.jpg",
        upload_status=PortfolioImage.UploadStatus.QUEUED,
        quality_status=PortfolioImage.QualityStatus.PENDING_ANALYSIS,
        visibility_status=PortfolioImage.VisibilityStatus.PRIVATE,
    )

    class Analyzer:
        def analyze(self, *, storage_path, media_type, file_url=None):
            assert storage_path is None
            assert file_url == "https://res.cloudinary.com/demo/remote.jpg"
            return type(
                "QualityResult",
                (),
                {
                    "status": "passed",
                    "score": 90,
                    "summary": "Image quality preflight passed.",
                    "width": 1200,
                    "height": 800,
                    "duration_seconds": None,
                },
            )()

    monkeypatch.setattr("tasks.image_tasks.MediaQualityAnalyzer", Analyzer)
    monkeypatch.setattr(
        "tasks.image_tasks.default_storage.open",
        lambda *_args, **_kwargs: (_ for _ in ()).throw(AssertionError("remote media should not open temp file")),
    )
    monkeypatch.setattr(
        "tasks.image_tasks.CloudinaryAdapter.upload_image",
        lambda *_args, **_kwargs: (_ for _ in ()).throw(AssertionError("remote media should not be re-uploaded")),
    )

    result = process_vendor_portfolio_media_task.run(str(image.id))

    image.refresh_from_db()
    assert result["status"] == "completed"
    assert image.upload_status == PortfolioImage.UploadStatus.UPLOADED
    assert image.quality_status == PortfolioImage.QualityStatus.PASSED
    assert image.visibility_status == PortfolioImage.VisibilityStatus.WAITING_APPROVAL
    assert image.cloudinary_secure_url == "https://res.cloudinary.com/demo/remote.jpg"
    assert image.analyzer_score == 90
    assert image.analyzer_summary == "Image quality preflight passed."
    assert image.temp_upload_path is None


@pytest.mark.django_db
def test_portfolio_task_marks_missing_url_and_temp_file_unrecoverable():
    vendor = create_vendor_profile()
    image = PortfolioImage.objects.create(
        vendor=vendor,
        upload_status=PortfolioImage.UploadStatus.QUEUED,
        quality_status=PortfolioImage.QualityStatus.PENDING_ANALYSIS,
        visibility_status=PortfolioImage.VisibilityStatus.WAITING_APPROVAL,
    )

    result = process_vendor_portfolio_media_task.run(str(image.id))

    image.refresh_from_db()
    assert result["status"] == "failed"
    assert image.upload_status == PortfolioImage.UploadStatus.FAILED
    assert image.visibility_status == PortfolioImage.VisibilityStatus.PRIVATE
    assert image.upload_error == "Uploaded media is no longer available."
