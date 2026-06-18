import uuid
from io import StringIO

import pytest
from django.core.files.base import ContentFile
from django.core.management import call_command
from django.core.files.storage import default_storage
from django.core.files.uploadedfile import SimpleUploadedFile
from django.test import override_settings
from django.urls import reverse
from rest_framework.test import APIClient

from django_app.identity.models import User
from django_app.vendors.models import PortfolioImage, VerificationDocument, VendorProfile as DjangoProfile
from tasks.document_tasks import process_vendor_verification_document_task
from tasks.image_tasks import upload_vendor_portfolio_image_task

pytestmark = pytest.mark.django_db


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

    def test_create_profile_success(self):
        url = reverse("vendor-profile")
        data = {
            "business_name": "My Photo Studio",
            "category": "photography",
            "description": "Best photos in town",
            "service_area": "Kigali, Rwanda",
            "contact_email": "studio@example.com",
            "contact_phone": "+250788123456",
            "website": "https://example.com",
        }
        response = self.client.post(url, data, format="json")
        assert response.status_code == 201
        assert response.data["business_name"] == "My Photo Studio"
        assert DjangoProfile.objects.count() == 1

    def test_create_profile_missing_required_field_returns_400(self):
        data = {
            "business_name": "",
            "category": "photography",
            "description": "Best photos in town",
            "service_area": "Kigali, Rwanda",
            "contact_email": "studio@example.com",
            "contact_phone": "+250788123456",
        }

        response = self.client.post(reverse("vendor-profile"), data, format="json")

        assert response.status_code == 400
        assert "business_name" in response.data

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
        assert "custom_category" in response.data

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
        url = reverse("vendor-submit")
        response = self.client.post(url)
        assert response.status_code == 200
        profile.refresh_from_db()
        assert profile.status == "pending_review"
        assert profile.submitted_at is not None
        assert response.data["status"] == "pending_review"
        assert response.data["business_name"] == "Test"

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
        assert response.data["redirect_to"] == "/vendor/profile"

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
            "tasks.image_tasks.upload_vendor_portfolio_image_task.delay",
            lambda image_id: queued.append(image_id),
        )

        url = reverse("portfolio-list")
        image = SimpleUploadedFile("portfolio.jpg", b"fake-image", content_type="image/jpeg")
        response = self.client.post(url, {"image": image, "caption": "My photo"}, format="multipart")

        assert response.status_code == 202
        assert response.data["status"] == "processing"
        assert response.data["job_id"]
        assert response.data["message"] == "Portfolio image upload is processing."
        assert self.profile.images.count() == 1
        stored = self.profile.images.get()
        assert stored.upload_status == PortfolioImage.UploadStatus.PENDING
        assert stored.original_filename == "portfolio.jpg"
        assert stored.temp_upload_path
        assert queued == [str(stored.id)]

    def test_upload_invalid_file_type_returns_400(self):
        image = SimpleUploadedFile("portfolio.txt", b"not-image", content_type="text/plain")

        response = self.client.post(reverse("portfolio-list"), {"image": image}, format="multipart")

        assert response.status_code == 400
        assert "Unsupported image type" in response.data["detail"]
        assert self.profile.images.count() == 0

    @override_settings(VENDOR_PORTFOLIO_MAX_UPLOAD_SIZE=4)
    def test_upload_oversized_file_returns_400(self):
        image = SimpleUploadedFile("portfolio.jpg", b"too-large", content_type="image/jpeg")

        response = self.client.post(reverse("portfolio-list"), {"image": image}, format="multipart")

        assert response.status_code == 400
        assert "too large" in response.data["detail"]
        assert self.profile.images.count() == 0

    def test_list_includes_upload_status_for_existing_completed_images(self):
        PortfolioImage.objects.create(
            vendor=self.profile,
            public_id="portfolio/existing",
            secure_url="https://example.com/existing.jpg",
            caption="Existing",
            upload_status=PortfolioImage.UploadStatus.COMPLETED,
        )

        response = self.client.get(reverse("portfolio-list"))

        assert response.status_code == 200
        assert response.data[0]["secure_url"] == "https://example.com/existing.jpg"
        assert response.data[0]["upload_status"] == "completed"

    def test_celery_task_marks_image_completed_on_cloudinary_success(self, monkeypatch):
        temp_path = default_storage.save("vendor_portfolio_uploads/test/portfolio.jpg", ContentFile(b"image"))
        image = PortfolioImage.objects.create(
            vendor=self.profile,
            caption="Queued",
            upload_status=PortfolioImage.UploadStatus.PENDING,
            original_filename="portfolio.jpg",
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
        assert image.upload_status == PortfolioImage.UploadStatus.COMPLETED
        assert image.secure_url == "https://res.cloudinary.com/demo/portfolio.jpg"
        assert image.public_id == "vendor_portfolio/portfolio"
        assert image.temp_upload_path is None
        assert not default_storage.exists(temp_path)

    def test_celery_task_marks_image_failed_on_cloudinary_failure(self, monkeypatch):
        temp_path = default_storage.save("vendor_portfolio_uploads/test/failure.jpg", ContentFile(b"image"))
        image = PortfolioImage.objects.create(
            vendor=self.profile,
            caption="Queued",
            upload_status=PortfolioImage.UploadStatus.PENDING,
            original_filename="failure.jpg",
            temp_upload_path=temp_path,
        )

        monkeypatch.setattr(
            "infrastructure.adapters.cloudinary_adapter.CloudinaryAdapter.upload_image",
            lambda self, file, fallback_to_storage=False: (_ for _ in ()).throw(RuntimeError("network down")),
        )

        upload_vendor_portfolio_image_task.request.retries = upload_vendor_portfolio_image_task.max_retries
        result = upload_vendor_portfolio_image_task.run(str(image.id))

        image.refresh_from_db()
        assert result["status"] == "failed"
        assert image.upload_status == PortfolioImage.UploadStatus.FAILED
        assert image.upload_error == "Portfolio image upload failed. Please try again."

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
