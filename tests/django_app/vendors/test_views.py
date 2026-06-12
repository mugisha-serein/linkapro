import uuid
import pytest
from django.test import override_settings
from django.urls import reverse
from rest_framework.test import APIClient

from django_app.identity.models import User
from django_app.vendors.models import VendorProfile as DjangoProfile

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

    def test_upload_image_sync(self, monkeypatch):
        # Mock Cloudinary upload to avoid network call
        def mock_upload(self, file):
            return {"public_id": "fake_id", "secure_url": "https://fake.url/img.jpg"}
        monkeypatch.setattr(
            "infrastructure.adapters.cloudinary_adapter.CloudinaryAdapter.upload_image",
            mock_upload
        )

        url = reverse("portfolio-list")
        with open(__file__, "rb") as f:
            data = {"image": f, "caption": "My photo"}
            response = self.client.post(url, data, format="multipart")
        assert response.status_code == 201
        assert response.data["secure_url"] == "https://fake.url/img.jpg"
        assert self.profile.images.count() == 1

    @override_settings(CLOUDINARY_CLOUD_NAME="", CLOUDINARY_API_KEY="", CLOUDINARY_API_SECRET="")
    def test_upload_image_falls_back_to_local_storage_when_cloudinary_unavailable(self):
        url = reverse("portfolio-list")
        with open(__file__, "rb") as f:
            response = self.client.post(url, {"image": f, "caption": "My photo"}, format="multipart")

        assert response.status_code == 201
        assert response.data["secure_url"].startswith("/media/")
        assert self.profile.images.count() == 1

    def test_delete_image_not_found(self):
        url = reverse("portfolio-detail", args=[uuid.uuid4()])
        response = self.client.delete(url)
        assert response.status_code == 404
