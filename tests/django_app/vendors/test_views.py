import uuid
import importlib
from datetime import timedelta
from io import BytesIO, StringIO

import pytest
from django.apps import apps
from django.core.files.base import ContentFile
from django.core.management import call_command
from django.core.files.storage import default_storage
from django.core.files.uploadedfile import SimpleUploadedFile
from django.test import override_settings
from django.urls import reverse
from django.utils import timezone
from rest_framework.test import APIClient

from django_app.identity.models import User
from django_app.vendors.models import Inquiry, PortfolioImage, ServicePackage, VerificationDocument, VendorProfile as DjangoProfile
from tasks.document_tasks import process_vendor_verification_document_task
from tasks.image_tasks import process_vendor_portfolio_media_task, upload_vendor_portfolio_image_task

pytestmark = pytest.mark.django_db
clear_private_portfolio_preview_urls = importlib.import_module(
    "django_app.vendors.migrations.0010_clear_portfolio_local_preview_urls"
).clear_private_portfolio_preview_urls


class TestVendorProfileViews:
    @pytest.fixture(autouse=True)
    def setup(self):
        self.client = APIClient()
        self.user = User.objects.create_user(
            email="vendor@example.com",
            password="pass123",
            first_name="Vendor",
            last_name="User",
            role="vendor",
        )
        self.client.force_authenticate(user=self.user)

    def test_get_profile_404_when_none(self):
        url = reverse("vendor-profile")
        response = self.client.get(url)
        assert response.status_code == 404
        assert response.data["onboarding"]["profile_status"] == "missing"
        assert response.data["redirect_to"] == "/vendor/profile/setup"

    def test_get_profile_status_returns_missing_contract_when_none(self):
        response = self.client.get(reverse("vendor-profile-status"))

        assert response.status_code == 200
        assert response.data["profile"] is None
        assert response.data["onboarding"]["profile_status"] == "missing"
        assert response.data["onboarding"]["redirect_to"] == "/vendor/profile/setup"

    def test_create_profile_success(self):
        url = reverse("vendor-profile")
        data = {
            "business_name": "My Photo Studio",
            "category": "photography",
            "description": "Best photography services in town",
            "service_area": "Kigali, Rwanda",
            "contact_email": "studio@example.com",
            "contact_phone": "+250788123456",
            "website": "https://example.com",
        }
        response = self.client.post(url, data, format="json")
        assert response.status_code == 201
        assert response.data["business_name"] == "My Photo Studio"
        assert response.data["onboarding"]["profile_status"] == "draft"
        assert response.data["onboarding"]["can_access_dashboard"] is False
        assert DjangoProfile.objects.count() == 1

    def test_create_profile_missing_required_field_returns_400(self):
        data = {
            "business_name": "",
            "category": "photography",
            "description": "Best photography services in town",
            "service_area": "Kigali, Rwanda",
            "contact_email": "studio@example.com",
            "contact_phone": "+250788123456",
        }

        response = self.client.post(reverse("vendor-profile"), data, format="json")

        assert response.status_code == 400
        assert "business_name" in response.data["field_errors"]

    def test_create_profile_other_category_requires_custom_category(self):
        data = {
            "business_name": "My Studio",
            "category": "other",
            "custom_category": "",
            "description": "Best creative services in town",
            "service_area": "Kigali, Rwanda",
            "contact_email": "studio@example.com",
            "contact_phone": "+250788123456",
        }

        response = self.client.post(reverse("vendor-profile"), data, format="json")

        assert response.status_code == 400
        assert response.data["field_errors"]["custom_category"] == [
            "Tell us what service you provide when choosing Other."
        ]

    def test_create_profile_other_category_with_custom_category_succeeds(self):
        data = {
            "business_name": "My Studio",
            "category": "other",
            "custom_category": "Cake sculpture",
            "description": "Best creative services in town",
            "service_area": "Kigali, Rwanda",
            "contact_email": "studio@example.com",
            "contact_phone": "+250788123456",
        }

        response = self.client.post(reverse("vendor-profile"), data, format="json")

        assert response.status_code == 201
        assert response.data["category"] == "other"
        assert response.data["custom_category"] == "Cake sculpture"
        assert DjangoProfile.objects.get().custom_category == "Cake sculpture"

    def test_create_duplicate_profile_fails(self):
        # Create first profile
        DjangoProfile.objects.create(
            user=self.user,
            business_name="First",
            category="photography",
            description="A complete vendor description.",
            service_area="area",
            contact_email="first@example.com",
            contact_phone="123",
        )
        url = reverse("vendor-profile")
        data = {
            "business_name": "Second",
            "category": "catering",
            "description": "desc",
            "service_area": "area",
            "contact_email": "second@example.com",
            "contact_phone": "456",
        }
        response = self.client.post(url, data, format="json")
        assert response.status_code == 400
        assert "already has" in response.data["detail"]

    def test_submit_for_review(self):
        profile = DjangoProfile.objects.create(
            user=self.user,
            business_name="Test",
            category="photography",
            description="A complete vendor description.",
            service_area="area",
            contact_email="test@example.com",
            contact_phone="123",
            status="draft",
        )
        VerificationDocument.objects.create(
            vendor=profile,
            document_type=VerificationDocument.DocumentType.TRADE_LICENSE,
            original_filename="license.pdf",
            mime_type="application/pdf",
            file_size=100,
            upload_status=VerificationDocument.UploadStatus.QUEUED,
            verification_status=VerificationDocument.VerificationStatus.PENDING_REVIEW,
        )
        url = reverse("vendor-submit")
        response = self.client.post(url)
        assert response.status_code == 200
        profile.refresh_from_db()
        assert profile.status == "pending_review"
        assert profile.submitted_at is not None
        assert response.data["status"] == "pending_review"
        assert response.data["business_name"] == "Test"
        assert response.data["onboarding"]["can_access_dashboard"] is True
        assert response.data["onboarding"]["marketplace_visible"] is False

    def test_submit_requires_verification_document(self):
        DjangoProfile.objects.create(
            user=self.user,
            business_name="Test",
            category="photography",
            description="A complete vendor description.",
            service_area="area",
            contact_email="test@example.com",
            contact_phone="123",
            status="draft",
        )

        response = self.client.post(reverse("vendor-submit"))

        assert response.status_code == 400
        assert response.data["code"] == "vendor_verification_document_required"
        assert response.data["onboarding"]["can_submit_for_review"] is True

    def test_incomplete_submit_remains_draft(self):
        profile = DjangoProfile.objects.create(
            user=self.user,
            business_name="Test",
            category="photography",
            description="Too short",
            service_area="area",
            contact_email="test@example.com",
            contact_phone="123",
            status="draft",
        )

        response = self.client.post(reverse("vendor-submit"))

        assert response.status_code == 403
        assert response.data["code"] == "vendor_profile_incomplete"
        assert "description" in response.data["field_errors"]
        profile.refresh_from_db()
        assert profile.status == "draft"

    def test_vendor_cannot_self_approve_from_profile_update(self):
        profile = DjangoProfile.objects.create(
            user=self.user,
            business_name="Test",
            category="photography",
            description="A complete vendor description.",
            service_area="area",
            contact_email="test@example.com",
            contact_phone="123",
            status="draft",
        )

        response = self.client.patch(
            reverse("vendor-profile"),
            {"status": "approved", "business_name": "Updated"},
            format="json",
        )

        assert response.status_code == 200
        profile.refresh_from_db()
        assert profile.status == "draft"
        assert profile.business_name == "Updated"

    def test_draft_vendor_cannot_access_dashboard_summary(self):
        DjangoProfile.objects.create(
            user=self.user,
            business_name="Test",
            category="photography",
            description="A complete vendor description.",
            service_area="area",
            contact_email="test@example.com",
            contact_phone="123",
            status="draft",
        )

        response = self.client.get(reverse("vendor-dashboard-summary"))

        assert response.status_code == 403
        assert response.data["code"] == "vendor_profile_incomplete"
        assert response.data["redirect_to"] == "/vendor/profile/setup"

    def test_pending_vendor_can_access_dashboard_summary(self):
        DjangoProfile.objects.create(
            user=self.user,
            business_name="Test",
            category="photography",
            description="A complete vendor description.",
            service_area="area",
            contact_email="test@example.com",
            contact_phone="123",
            status="pending_review",
        )

        response = self.client.get(reverse("vendor-dashboard-summary"))

        assert response.status_code == 200
        assert response.data["account_status"] == "pending_review"

    def test_activity_without_limit_returns_200(self):
        profile = DjangoProfile.objects.create(
            user=self.user,
            business_name="Test",
            category="photography",
            description="A complete vendor description.",
            service_area="area",
            contact_email="test@example.com",
            contact_phone="123",
            status="pending_review",
        )
        Inquiry.objects.create(vendor=profile, client_name="Client", client_email="client@example.com", message="Need help")

        response = self.client.get(reverse("vendor-activity"))

        assert response.status_code == 200
        assert len(response.data) == 1

    def test_activity_with_valid_limit_returns_200(self):
        profile = DjangoProfile.objects.create(
            user=self.user,
            business_name="Test",
            category="photography",
            description="A complete vendor description.",
            service_area="area",
            contact_email="test@example.com",
            contact_phone="123",
            status="pending_review",
        )
        for index in range(3):
            Inquiry.objects.create(
                vendor=profile,
                client_name=f"Client {index}",
                client_email=f"client{index}@example.com",
                message="Need help",
            )

        response = self.client.get(reverse("vendor-activity"), {"limit": "2"})

        assert response.status_code == 200
        assert len(response.data) == 2

    @pytest.mark.parametrize("limit", ["abc", "0", "-1", "1000"])
    def test_activity_invalid_limit_returns_structured_400(self, limit):
        DjangoProfile.objects.create(
            user=self.user,
            business_name="Test",
            category="photography",
            description="A complete vendor description.",
            service_area="area",
            contact_email="test@example.com",
            contact_phone="123",
            status="pending_review",
        )

        response = self.client.get(reverse("vendor-activity"), {"limit": limit})

        assert response.status_code == 400
        assert response.data["success"] is False
        assert response.data["code"] == "vendor_activity_limit_invalid"
        assert response.data["field_errors"] == {"limit": ["Enter an integer from 1 to 100."]}

    def test_rejected_vendor_cannot_access_dashboard_summary_until_resubmitted(self):
        DjangoProfile.objects.create(
            user=self.user,
            business_name="Test",
            category="photography",
            description="A complete vendor description.",
            service_area="area",
            contact_email="test@example.com",
            contact_phone="123",
            status="rejected",
        )

        response = self.client.get(reverse("vendor-dashboard-summary"))

        assert response.status_code == 403
        assert response.data["code"] == "vendor_profile_incomplete"

    def test_rejected_vendor_can_resubmit_complete_profile(self):
        profile = DjangoProfile.objects.create(
            user=self.user,
            business_name="Test",
            category="photography",
            description="A complete vendor description.",
            service_area="area",
            contact_email="test@example.com",
            contact_phone="123",
            status="rejected",
            rejection_reason="Needs details",
        )
        VerificationDocument.objects.create(
            vendor=profile,
            document_type=VerificationDocument.DocumentType.TRADE_LICENSE,
            original_filename="license.pdf",
            mime_type="application/pdf",
            file_size=100,
            upload_status=VerificationDocument.UploadStatus.PROCESSING_DEFERRED,
            verification_status=VerificationDocument.VerificationStatus.PENDING_REVIEW,
        )

        response = self.client.post(reverse("vendor-submit"))

        assert response.status_code == 200
        profile.refresh_from_db()
        assert profile.status == "pending_review"

    def test_suspended_vendor_cannot_access_dashboard_summary(self):
        DjangoProfile.objects.create(
            user=self.user,
            business_name="Test",
            category="photography",
            description="A complete vendor description.",
            service_area="area",
            contact_email="test@example.com",
            contact_phone="123",
            status="suspended",
        )

        response = self.client.get(reverse("vendor-dashboard-summary"))

        assert response.status_code == 403
        assert response.data["code"] == "vendor_suspended"

    def test_suspended_vendor_cannot_submit_profile_for_review(self):
        profile = DjangoProfile.objects.create(
            user=self.user,
            business_name="Test",
            category="photography",
            description="A complete vendor description.",
            service_area="area",
            contact_email="test@example.com",
            contact_phone="123",
            status="suspended",
        )

        response = self.client.post(reverse("vendor-submit"))

        assert response.status_code == 400
        profile.refresh_from_db()
        assert profile.status == "suspended"


class TestPortfolioImageViews:
    @pytest.fixture(autouse=True)
    def setup(self):
        self.client = APIClient()
        self.user = User.objects.create_user(
            email="vendor@example.com",
            password="pass123",
            first_name="Vendor",
            last_name="User",
            role="vendor",
        )
        self.client.force_authenticate(user=self.user)
        self.profile = DjangoProfile.objects.create(
            user=self.user,
            business_name="Test",
            category="photography",
            description="A complete vendor description.",
            service_area="area",
            contact_email="test@example.com",
            contact_phone="123",
            status="pending_review",
        )

    def test_list_images_empty(self):
        url = reverse("portfolio-list")
        response = self.client.get(url)
        assert response.status_code == 200
        assert response.data == []

    def test_upload_image_returns_202_and_queues_task(self, monkeypatch):
        queued = []
        monkeypatch.setattr(
            "tasks.image_tasks.process_vendor_portfolio_media_task.delay",
            lambda image_id: queued.append(image_id),
        )

        url = reverse("portfolio-list")
        image = SimpleUploadedFile("portfolio.jpg", valid_image_bytes(), content_type="image/jpeg")
        response = self.client.post(url, {"media": image, "caption": "My photo"}, format="multipart")

        assert response.status_code == 202
        assert response.data["status"] == "queued"
        assert response.data["processing_deferred"] is False
        assert response.data["job_id"]
        assert response.data["message"] == "Portfolio item received. Review will continue automatically."
        assert response.data["item"]["local_preview_url"] is None
        assert response.data["item"]["display_url"] is None
        assert "temp_upload_path" not in response.data["item"]
        assert self.profile.images.count() == 1
        stored = self.profile.images.get()
        assert stored.media_type == PortfolioImage.MediaType.IMAGE
        assert stored.upload_status == PortfolioImage.UploadStatus.QUEUED
        assert stored.quality_status == PortfolioImage.QualityStatus.PENDING_ANALYSIS
        assert stored.visibility_status == PortfolioImage.VisibilityStatus.PRIVATE
        assert stored.original_filename == "portfolio.jpg"
        assert stored.local_preview_url is None
        assert stored.temp_upload_path
        assert queued == [str(stored.id)]

    @pytest.mark.parametrize(
        ("filename", "content_type", "image_format"),
        [
            ("portfolio.png", "image/png", "PNG"),
            ("portfolio.webp", "image/webp", "WEBP"),
        ],
    )
    def test_upload_valid_png_and_webp_return_202(self, filename, content_type, image_format, monkeypatch):
        monkeypatch.setattr(
            "tasks.image_tasks.process_vendor_portfolio_media_task.delay",
            lambda image_id: None,
        )
        image = SimpleUploadedFile(
            filename,
            valid_image_bytes(image_format=image_format),
            content_type=content_type,
        )

        response = self.client.post(reverse("portfolio-list"), {"media": image}, format="multipart")

        assert response.status_code == 202
        stored = PortfolioImage.objects.get()
        assert stored.media_type == PortfolioImage.MediaType.IMAGE
        assert stored.width == 800
        assert stored.height == 600

    def test_upload_video_returns_202_when_under_10mb(self, monkeypatch):
        queued = []
        monkeypatch.setattr(
            "tasks.image_tasks.process_vendor_portfolio_media_task.delay",
            lambda image_id: queued.append(image_id),
        )
        video = SimpleUploadedFile("highlight.mp4", b"\x00\x00\x00\x18ftypmp42" + b"0" * 128, content_type="video/mp4")

        response = self.client.post(reverse("portfolio-list"), {"media": video}, format="multipart")

        assert response.status_code == 202
        stored = PortfolioImage.objects.get()
        assert stored.media_type == PortfolioImage.MediaType.VIDEO
        assert stored.upload_status == PortfolioImage.UploadStatus.QUEUED
        assert queued == [str(stored.id)]

    def test_upload_webm_video_returns_202_when_under_10mb(self, monkeypatch):
        monkeypatch.setattr(
            "tasks.image_tasks.process_vendor_portfolio_media_task.delay",
            lambda image_id: None,
        )
        video = SimpleUploadedFile("highlight.webm", b"\x1aE\xdf\xa3" + b"0" * 128, content_type="video/webm")

        response = self.client.post(reverse("portfolio-list"), {"media": video}, format="multipart")

        assert response.status_code == 202
        assert PortfolioImage.objects.get().media_type == PortfolioImage.MediaType.VIDEO

    def test_upload_video_over_10mb_returns_400(self):
        video = SimpleUploadedFile("large.mp4", b"\x00\x00\x00\x18ftypmp42" + (b"0" * (10 * 1024 * 1024 + 1)), content_type="video/mp4")

        response = self.client.post(reverse("portfolio-list"), {"media": video}, format="multipart")

        assert response.status_code == 400
        assert response.data["code"] == "portfolio_media_invalid"
        assert response.data["field_errors"]["media"][0] == "Videos must be 10MB or smaller."

    def test_upload_invalid_file_type_returns_400(self):
        image = SimpleUploadedFile("portfolio.txt", b"not-image", content_type="text/plain")

        response = self.client.post(reverse("portfolio-list"), {"image": image}, format="multipart")

        assert response.status_code == 400
        assert response.data["code"] == "portfolio_media_invalid"
        assert "Only JPEG, PNG, WEBP images or MP4/WEBM videos are allowed." in response.data["field_errors"]["media"][0]
        assert self.profile.images.count() == 0

    def test_upload_heic_image_returns_structured_400(self):
        image = SimpleUploadedFile("portfolio.heic", b"heic-data", content_type="image/heic")

        response = self.client.post(reverse("portfolio-list"), {"media": image}, format="multipart")

        assert response.status_code == 400
        assert response.data["field_errors"]["media"][0] == "Only JPEG, PNG, WEBP images or MP4/WEBM videos are allowed."

    @override_settings(VENDOR_PORTFOLIO_MAX_UPLOAD_SIZE=4)
    def test_upload_oversized_file_returns_400(self):
        image = SimpleUploadedFile("portfolio.jpg", b"too-large", content_type="image/jpeg")

        response = self.client.post(reverse("portfolio-list"), {"media": image}, format="multipart")

        assert response.status_code == 400
        assert "too large" in response.data["field_errors"]["media"][0]
        assert self.profile.images.count() == 0

    def test_upload_low_resolution_image_returns_400(self):
        image = SimpleUploadedFile("tiny.jpg", valid_image_bytes(size=(320, 240)), content_type="image/jpeg")

        response = self.client.post(reverse("portfolio-list"), {"media": image}, format="multipart")

        assert response.status_code == 400
        assert response.data["field_errors"]["media"][0] == "This image is too small. Upload a clearer, higher-resolution photo."

    def test_corrupt_video_returns_structured_400(self):
        video = SimpleUploadedFile("highlight.mp4", b"not-a-real-video", content_type="video/mp4")

        response = self.client.post(reverse("portfolio-list"), {"media": video}, format="multipart")

        assert response.status_code == 400
        assert response.data["field_errors"]["media"][0] == "This video could not be read. Upload a valid MP4, WEBM, or MOV highlight video."

    def test_draft_vendor_with_saved_profile_can_upload_private_media(self, monkeypatch):
        self.profile.status = DjangoProfile.Status.DRAFT
        self.profile.save(update_fields=["status", "updated_at"])
        monkeypatch.setattr(
            "tasks.image_tasks.process_vendor_portfolio_media_task.delay",
            lambda image_id: None,
        )
        image = SimpleUploadedFile("draft.jpg", valid_image_bytes(), content_type="image/jpeg")

        response = self.client.post(reverse("portfolio-list"), {"media": image}, format="multipart")

        assert response.status_code == 202
        stored = PortfolioImage.objects.get()
        assert stored.visibility_status == PortfolioImage.VisibilityStatus.PRIVATE

    def test_rejected_vendor_upload_blocked_with_onboarding_contract(self):
        self.profile.status = DjangoProfile.Status.REJECTED
        self.profile.rejection_reason = "Please update your profile."
        self.profile.save(update_fields=["status", "rejection_reason", "updated_at"])
        image = SimpleUploadedFile("rejected.jpg", valid_image_bytes(), content_type="image/jpeg")

        response = self.client.post(reverse("portfolio-list"), {"media": image}, format="multipart")

        assert response.status_code == 403
        assert response.data["field_errors"]["media"][0] == "Please update your profile."
        assert response.data["onboarding"]["profile_status"] == "rejected"

    def test_list_includes_upload_status_for_existing_completed_images(self):
        PortfolioImage.objects.create(
            vendor=self.profile,
            public_id="portfolio/existing",
            secure_url="https://example.com/existing.jpg",
            caption="Existing",
            upload_status=PortfolioImage.UploadStatus.UPLOADED,
        )

        response = self.client.get(reverse("portfolio-list"))

        assert response.status_code == 200
        assert response.data[0]["secure_url"] == "https://example.com/existing.jpg"
        assert response.data[0]["display_url"] == "https://example.com/existing.jpg"
        assert response.data[0]["local_preview_url"] is None
        assert response.data[0]["upload_status"] == "uploaded"

    def test_list_does_not_expose_existing_broken_local_preview_url(self):
        PortfolioImage.objects.create(
            vendor=self.profile,
            public_id="",
            secure_url="",
            local_preview_url="/media/vendor_portfolio_uploads/test/broken.jpg",
            caption="Processing",
            upload_status=PortfolioImage.UploadStatus.QUEUED,
            visibility_status=PortfolioImage.VisibilityStatus.PRIVATE,
        )

        response = self.client.get(reverse("portfolio-list"))

        assert response.status_code == 200
        assert response.data[0]["secure_url"] is None
        assert response.data[0]["display_url"] is None
        assert response.data[0]["local_preview_url"] is None

    def test_cleanup_migration_clears_broken_local_preview_urls(self):
        broken = PortfolioImage.objects.create(
            vendor=self.profile,
            local_preview_url="/media/vendor_portfolio_uploads/test/broken.jpg",
            upload_status=PortfolioImage.UploadStatus.QUEUED,
        )
        cloudinary = PortfolioImage.objects.create(
            vendor=self.profile,
            cloudinary_secure_url="https://res.cloudinary.com/demo/portfolio.jpg",
            local_preview_url="/media/vendor_portfolio_uploads/test/old.jpg",
            upload_status=PortfolioImage.UploadStatus.UPLOADED,
        )

        clear_private_portfolio_preview_urls(apps, None)

        broken.refresh_from_db()
        cloudinary.refresh_from_db()
        assert broken.local_preview_url is None
        assert cloudinary.cloudinary_secure_url == "https://res.cloudinary.com/demo/portfolio.jpg"
        assert cloudinary.local_preview_url is None

    def test_celery_task_marks_image_completed_on_cloudinary_success(self, monkeypatch):
        temp_path = default_storage.save("vendor_portfolio_uploads/test/portfolio.jpg", ContentFile(valid_image_bytes()))
        image = PortfolioImage.objects.create(
            vendor=self.profile,
            caption="Queued",
            upload_status=PortfolioImage.UploadStatus.QUEUED,
            quality_status=PortfolioImage.QualityStatus.PENDING_ANALYSIS,
            visibility_status=PortfolioImage.VisibilityStatus.PRIVATE,
            original_filename="portfolio.jpg",
            media_type=PortfolioImage.MediaType.IMAGE,
            local_preview_url="/media/vendor_portfolio_uploads/test/portfolio.jpg",
            temp_upload_path=temp_path,
        )

        monkeypatch.setattr(
            "infrastructure.adapters.cloudinary_adapter.CloudinaryAdapter.upload_image",
            lambda self, file, fallback_to_storage=False: {
                "public_id": "vendor_portfolio/portfolio",
                "secure_url": "https://res.cloudinary.com/demo/portfolio.jpg",
            },
        )

        result = upload_vendor_portfolio_image_task.run(str(image.id))

        image.refresh_from_db()
        assert result["status"] == "completed"
        assert image.upload_status == PortfolioImage.UploadStatus.UPLOADED
        assert image.quality_status == PortfolioImage.QualityStatus.PASSED
        assert image.visibility_status == PortfolioImage.VisibilityStatus.WAITING_APPROVAL
        assert image.secure_url == "https://res.cloudinary.com/demo/portfolio.jpg"
        assert image.public_id == "vendor_portfolio/portfolio"
        assert image.cloudinary_secure_url == "https://res.cloudinary.com/demo/portfolio.jpg"
        assert image.local_preview_url is None
        assert image.temp_upload_path is None
        assert not default_storage.exists(temp_path)

    def test_celery_task_marks_image_failed_on_cloudinary_failure(self, monkeypatch):
        temp_path = default_storage.save("vendor_portfolio_uploads/test/failure.jpg", ContentFile(valid_image_bytes()))
        image = PortfolioImage.objects.create(
            vendor=self.profile,
            caption="Queued",
            upload_status=PortfolioImage.UploadStatus.QUEUED,
            original_filename="failure.jpg",
            media_type=PortfolioImage.MediaType.IMAGE,
            local_preview_url="/media/vendor_portfolio_uploads/test/failure.jpg",
            temp_upload_path=temp_path,
        )

        monkeypatch.setattr(
            "infrastructure.adapters.cloudinary_adapter.CloudinaryAdapter.upload_image",
            lambda self, file, fallback_to_storage=False: (_ for _ in ()).throw(RuntimeError("network down")),
        )

        process_vendor_portfolio_media_task.request.retries = process_vendor_portfolio_media_task.max_retries
        result = process_vendor_portfolio_media_task.run(str(image.id))

        image.refresh_from_db()
        assert result["status"] == "failed"
        assert image.upload_status == PortfolioImage.UploadStatus.FAILED
        assert image.upload_error == "Portfolio media upload failed. Please try again."
        assert image.local_preview_url is None

    def test_delete_image_soft_deletes_and_hides_from_default_list(self):
        image = PortfolioImage.objects.create(
            vendor=self.profile,
            public_id="portfolio/delete",
            secure_url="https://example.com/delete.jpg",
            caption="Delete me",
            upload_status=PortfolioImage.UploadStatus.UPLOADED,
            quality_status=PortfolioImage.QualityStatus.PASSED,
            visibility_status=PortfolioImage.VisibilityStatus.APPROVED,
            is_active=True,
        )

        response = self.client.delete(reverse("portfolio-detail", args=[image.id]))

        assert response.status_code == 200
        assert response.data["message"] == "Portfolio item removed from active listings."
        image = PortfolioImage.all_objects.get(id=image.id)
        assert image.is_deleted is True
        assert image.is_active is False
        assert image.deleted_by == self.user
        assert not PortfolioImage.objects.filter(id=image.id).exists()
        assert self.client.get(reverse("portfolio-list")).data == []

    def test_delete_image_not_found(self):
        url = reverse("portfolio-detail", args=[uuid.uuid4()])
        response = self.client.delete(url)
        assert response.status_code == 404


def valid_pdf_bytes() -> bytes:
    return (
        b"%PDF-1.4\n"
        b"1 0 obj\n<< /Type /Catalog /Pages 2 0 R >>\nendobj\n"
        b"2 0 obj\n<< /Type /Pages /Kids [3 0 R] /Count 1 >>\nendobj\n"
        b"3 0 obj\n<< /Type /Page /Parent 2 0 R /MediaBox [0 0 612 792] >>\nendobj\n"
        b"%%EOF\n"
    )


def valid_image_bytes(size=(800, 600), image_format="JPEG") -> bytes:
    from PIL import Image

    buffer = BytesIO()
    Image.new("RGB", size, color="white").save(buffer, format=image_format)
    return buffer.getvalue()


class TestVerificationDocumentViews:
    @pytest.fixture(autouse=True)
    def setup(self):
        self.client = APIClient()
        self.user = User.objects.create_user(
            email="vendor@example.com",
            password="pass123",
            first_name="Vendor",
            last_name="User",
            role="vendor",
        )
        self.client.force_authenticate(user=self.user)
        self.profile = DjangoProfile.objects.create(
            user=self.user,
            business_name="Test",
            category="photography",
            description="A complete vendor description.",
            service_area="area",
            contact_email="test@example.com",
            contact_phone="123",
            status="draft",
        )

    def test_pdf_verification_document_returns_202_and_queues_task(self, monkeypatch):
        queued = []
        monkeypatch.setattr(
            "tasks.document_tasks.process_vendor_verification_document_task.delay",
            lambda document_id: queued.append(document_id),
        )
        document_file = SimpleUploadedFile("license.pdf", valid_pdf_bytes(), content_type="application/pdf")

        response = self.client.post(
            reverse("vendor-verification-documents"),
            {"document_type": "trade_license", "document": document_file},
            format="multipart",
        )

        assert response.status_code == 202
        assert response.data["status"] == "queued"
        assert response.data["document_id"]
        assert response.data["processing_deferred"] is False
        assert response.data["message"] == "Document received. Verification will continue automatically."
        assert response.data["onboarding"]["profile_status"] == "draft"
        stored = VerificationDocument.objects.get()
        assert stored.upload_status == VerificationDocument.UploadStatus.QUEUED
        assert stored.verification_status == VerificationDocument.VerificationStatus.PENDING_REVIEW
        assert stored.mime_type == "application/pdf"
        assert stored.secure_url == ""
        assert stored.temp_upload_path
        assert queued == [str(stored.id)]

    def test_pdf_verification_document_returns_202_when_task_dispatch_fails(self, monkeypatch):
        def raise_broker_error(document_id):
            raise RuntimeError("broker unavailable")

        monkeypatch.setattr(
            "tasks.document_tasks.process_vendor_verification_document_task.delay",
            raise_broker_error,
        )
        document_file = SimpleUploadedFile("license.pdf", valid_pdf_bytes(), content_type="application/pdf")

        response = self.client.post(
            reverse("vendor-verification-documents"),
            {"document_type": "trade_license", "document": document_file},
            format="multipart",
        )

        assert response.status_code == 202
        assert response.data["status"] == "queued"
        assert response.data["processing_deferred"] is True
        assert response.data["message"] == "Document received. Verification will continue automatically."
        assert response.data["onboarding"]["can_access_dashboard"] is False
        stored = VerificationDocument.objects.get()
        assert stored.upload_status == VerificationDocument.UploadStatus.PROCESSING_DEFERRED
        assert stored.temp_upload_path

    def test_non_pdf_verification_document_returns_400(self):
        document_file = SimpleUploadedFile("license.png", b"not-pdf", content_type="image/png")

        response = self.client.post(
            reverse("vendor-verification-documents"),
            {"document_type": "trade_license", "document": document_file},
            format="multipart",
        )

        assert response.status_code == 400
        assert "document" in response.data
        assert VerificationDocument.objects.count() == 0

    def test_corrupt_pdf_verification_document_returns_400(self):
        document_file = SimpleUploadedFile("license.pdf", b"%PDF-1.4\nnot enough", content_type="application/pdf")

        response = self.client.post(
            reverse("vendor-verification-documents"),
            {"document_type": "trade_license", "document": document_file},
            format="multipart",
        )

        assert response.status_code == 400
        assert "document" in response.data
        assert VerificationDocument.objects.count() == 0

    @override_settings(VENDOR_VERIFICATION_DOCUMENT_MAX_SIZE_MB=0)
    def test_oversized_pdf_verification_document_returns_400(self):
        document_file = SimpleUploadedFile("license.pdf", valid_pdf_bytes(), content_type="application/pdf")

        response = self.client.post(
            reverse("vendor-verification-documents"),
            {"document_type": "trade_license", "document": document_file},
            format="multipart",
        )

        assert response.status_code == 400
        assert "too large" in response.data["document"][0]
        assert VerificationDocument.objects.count() == 0

    def test_celery_document_task_stores_cloudinary_metadata(self, monkeypatch):
        temp_path = default_storage.save("vendor_verification_uploads/test/license.pdf", ContentFile(valid_pdf_bytes()))
        document = VerificationDocument.objects.create(
            vendor=self.profile,
            document_type="trade_license",
            original_filename="license.pdf",
            mime_type="application/pdf",
            file_size=len(valid_pdf_bytes()),
            temp_upload_path=temp_path,
            upload_status=VerificationDocument.UploadStatus.QUEUED,
        )
        monkeypatch.setattr(
            "infrastructure.adapters.cloudinary_adapter.CloudinaryAdapter.upload_file",
            lambda self, file_obj, folder="exports", public_id=None, resource_type="raw": {
                "public_id": "vendor_verification_documents/license",
                "secure_url": "https://res.cloudinary.com/demo/license.pdf",
            },
        )

        result = process_vendor_verification_document_task.run(str(document.id))

        document.refresh_from_db()
        assert result["status"] == "completed"
        assert document.upload_status == VerificationDocument.UploadStatus.COMPLETED
        assert document.verification_status == VerificationDocument.VerificationStatus.NEEDS_MANUAL_REVIEW
        assert document.cloudinary_public_id == "vendor_verification_documents/license"
        assert document.cloudinary_secure_url == "https://res.cloudinary.com/demo/license.pdf"
        assert document.secure_url == "https://res.cloudinary.com/demo/license.pdf"
        assert document.odcr_status == "unavailable"
        assert document.temp_upload_path is None
        assert not default_storage.exists(temp_path)

    def test_celery_document_task_failure_marks_failed(self, monkeypatch):
        temp_path = default_storage.save("vendor_verification_uploads/test/fail.pdf", ContentFile(valid_pdf_bytes()))
        document = VerificationDocument.objects.create(
            vendor=self.profile,
            document_type="trade_license",
            original_filename="fail.pdf",
            mime_type="application/pdf",
            file_size=len(valid_pdf_bytes()),
            temp_upload_path=temp_path,
            upload_status=VerificationDocument.UploadStatus.QUEUED,
        )
        monkeypatch.setattr(
            "infrastructure.adapters.cloudinary_adapter.CloudinaryAdapter.upload_file",
            lambda self, file_obj, folder="exports", public_id=None, resource_type="raw": (_ for _ in ()).throw(RuntimeError("network down")),
        )

        process_vendor_verification_document_task.request.retries = process_vendor_verification_document_task.max_retries
        result = process_vendor_verification_document_task.run(str(document.id))

        document.refresh_from_db()
        assert result["status"] == "failed"
        assert document.upload_status == VerificationDocument.UploadStatus.FAILED
        assert document.verification_status == VerificationDocument.VerificationStatus.FAILED
        assert document.failure_reason == "Verification document upload failed. Please try again."

    def test_deferred_document_command_processes_staged_documents(self, monkeypatch):
        temp_path = default_storage.save("vendor_verification_uploads/test/deferred.pdf", ContentFile(valid_pdf_bytes()))
        document = VerificationDocument.objects.create(
            vendor=self.profile,
            document_type="trade_license",
            original_filename="deferred.pdf",
            mime_type="application/pdf",
            file_size=len(valid_pdf_bytes()),
            temp_upload_path=temp_path,
            upload_status=VerificationDocument.UploadStatus.PROCESSING_DEFERRED,
        )
        monkeypatch.setattr(
            "infrastructure.adapters.cloudinary_adapter.CloudinaryAdapter.upload_file",
            lambda self, file_obj, folder="exports", public_id=None, resource_type="raw": {
                "public_id": "vendor_verification_documents/deferred",
                "secure_url": "https://res.cloudinary.com/demo/deferred.pdf",
            },
        )
        stdout = StringIO()

        call_command("process_deferred_vendor_documents", "--process-inline", stdout=stdout)

        document.refresh_from_db()
        assert document.upload_status == VerificationDocument.UploadStatus.COMPLETED
        assert document.verification_status == VerificationDocument.VerificationStatus.NEEDS_MANUAL_REVIEW
        assert "processed=1" in stdout.getvalue()

    def test_existing_cloudinary_document_records_serialize(self):
        VerificationDocument.objects.create(
            vendor=self.profile,
            document_type="trade_license",
            original_filename="license.pdf",
            mime_type="application/pdf",
            file_size=123,
            secure_url="https://res.cloudinary.com/demo/license.pdf",
            cloudinary_secure_url="https://res.cloudinary.com/demo/license.pdf",
            upload_status=VerificationDocument.UploadStatus.COMPLETED,
            verification_status=VerificationDocument.VerificationStatus.PENDING_REVIEW,
        )

        response = self.client.get(reverse("vendor-verification-documents"))

        assert response.status_code == 200
        assert response.data[0]["original_filename"] == "license.pdf"
        assert response.data[0]["cloudinary_secure_url"] == "https://res.cloudinary.com/demo/license.pdf"
        assert response.data[0]["upload_status"] == "completed"
        assert response.data[0]["verification_status"] == "pending_review"


class TestServicePackageViews:
    @pytest.fixture(autouse=True)
    def setup(self):
        self.client = APIClient()
        self.user = User.objects.create_user(
            email="package-vendor@example.com",
            password="pass123",
            first_name="Package",
            last_name="Vendor",
            role="vendor",
        )
        self.client.force_authenticate(user=self.user)
        self.profile = DjangoProfile.objects.create(
            user=self.user,
            business_name="Package Studio",
            category="photography",
            description="A complete vendor description.",
            service_area="Kigali",
            contact_email="packages@example.com",
            contact_phone="123",
            status="approved",
        )

    def package_payload(self, **overrides):
        payload = {
            "name": "Standard Wedding Package",
            "description": "A detailed standard package with clear deliverables and timing.",
            "price": "25000.00",
            "currency": "RWF",
            "package_tier": "standard",
        }
        payload.update(overrides)
        return payload

    def test_vendor_creates_package_waiting_approval_and_sees_it(self):
        response = self.client.post(reverse("package-list"), self.package_payload(), format="json")

        assert response.status_code == 201
        assert response.data["approval_status"] == "waiting_approval"
        assert response.data["package_tier"] == "standard"
        package = ServicePackage.objects.get(id=response.data["id"])
        assert package.vendor == self.profile
        assert package.approval_status == ServicePackage.ApprovalStatus.WAITING_APPROVAL

        list_response = self.client.get(reverse("package-list"))
        assert list_response.status_code == 200
        assert [item["id"] for item in list_response.data] == [str(package.id)]

    def test_package_tier_rules_return_field_errors(self):
        response = self.client.post(
            reverse("package-list"),
            self.package_payload(
                name="Gold Guaranteed Success",
                description="Too short",
                price="999.00",
                package_tier="gold",
            ),
            format="json",
        )

        assert response.status_code == 400
        assert "description" in response.data
        assert "price" in response.data

    def test_editing_approved_package_before_cooldown_returns_contract_error(self):
        approved_at = timezone.now() - timedelta(days=1)
        next_allowed_at = approved_at + ServicePackage.vendor_edit_cooldown_delta()
        package = ServicePackage.objects.create(
            vendor=self.profile,
            name="Approved Premier Package",
            description="A premier package with enough detail for admin approval and planner clarity.",
            price="75000.00",
            currency="RWF",
            package_tier="premier",
            approval_status=ServicePackage.ApprovalStatus.APPROVED,
            is_active=True,
            last_approved_at=approved_at,
            next_vendor_edit_allowed_at=next_allowed_at,
        )

        response = self.client.patch(
            reverse("package-detail", args=[package.id]),
            {
                "description": "Updated premier package with enough detail to explain deliverables and booking terms.",
            },
            format="json",
        )

        package.refresh_from_db()
        assert response.status_code == 429
        assert response.data["success"] is False
        assert response.data["code"] == "vendor_package_edit_cooldown_active"
        assert response.data["cooldown_days"] == 15
        assert response.data["next_allowed_at"] == package.next_vendor_edit_allowed_at.isoformat()
        assert package.approval_status == ServicePackage.ApprovalStatus.APPROVED
        assert package.is_active is True
        assert package.description == "A premier package with enough detail for admin approval and planner clarity."

    def test_vendor_delete_soft_deletes_and_hides_package(self):
        package = ServicePackage.objects.create(
            vendor=self.profile,
            name="Soft Delete Package",
            description="A standard package with enough detail to pass validation.",
            price="15000.00",
            currency="RWF",
            package_tier="standard",
            approval_status=ServicePackage.ApprovalStatus.APPROVED,
            is_active=True,
        )

        response = self.client.delete(reverse("package-detail", args=[package.id]))

        assert response.status_code == 200
        assert response.data["message"] == "Package removed from active listings."
        package = ServicePackage.all_objects.get(id=package.id)
        assert package.is_deleted is True
        assert package.is_active is False
        assert package.deleted_by == self.user
        assert not ServicePackage.objects.filter(id=package.id).exists()
        assert self.client.get(reverse("package-list")).data == []

    def test_vendor_cannot_edit_or_delete_another_vendor_package(self):
        other_user = User.objects.create_user(email="other-vendor@example.com", password="pass123", role="vendor")
        other_profile = DjangoProfile.objects.create(
            user=other_user,
            business_name="Other Studio",
            category="decor",
            description="A complete vendor description.",
            service_area="Kigali",
            contact_email="other@example.com",
            contact_phone="456",
            status="approved",
        )
        package = ServicePackage.objects.create(
            vendor=other_profile,
            name="Other Package",
            description="A standard package with enough detail to pass validation.",
            price="15000.00",
            currency="RWF",
            package_tier="standard",
        )

        patch_response = self.client.patch(
            reverse("package-detail", args=[package.id]),
            {"name": "Hijacked Package"},
            format="json",
        )
        delete_response = self.client.delete(reverse("package-detail", args=[package.id]))

        package.refresh_from_db()
        assert patch_response.status_code == 404
        assert delete_response.status_code == 404
        assert package.name == "Other Package"
        assert package.is_deleted is False
