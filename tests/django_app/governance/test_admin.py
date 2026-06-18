import uuid
import pytest
from django.urls import reverse
from rest_framework.test import APIClient

from django_app.identity.models import User
from django_app.vendors.models import PortfolioImage, ServicePackage, VendorProfile

pytestmark = pytest.mark.django_db


class TestVendorApprovalAdmin:
    def test_approve_vendor_action(self, admin_client, monkeypatch):
        monkeypatch.setattr(
            "infrastructure.repos.django_vendor_profile_repository.sync_or_delete_vendor_projection",
            lambda vendor: {"status": "ok"},
        )
        admin_user = User.objects.create_superuser("admin@t.com", "pass")
        admin_client.force_login(admin_user)

        vendor_user = User.objects.create_user(email="v@t.com", password="p", role="vendor")
        vendor = VendorProfile.objects.create(
            user=vendor_user, business_name="V", category="photography",
            description="A complete vendor description.", service_area="a", contact_email="e", contact_phone="1",
            status="pending_review"
        )

        changelist_url = reverse("admin:vendors_vendorprofile_changelist")
        data = {"action": "approve_selected", "_selected_action": [vendor.pk]}
        response = admin_client.post(changelist_url, data, follow=True)

        vendor.refresh_from_db()
        assert vendor.status == "approved"
        assert response.status_code == 200

    def test_reject_vendor_action(self, admin_client, monkeypatch):
        monkeypatch.setattr(
            "infrastructure.repos.django_vendor_profile_repository.sync_or_delete_vendor_projection",
            lambda vendor: {"status": "ok"},
        )
        admin_user = User.objects.create_superuser("admin@t.com", "pass")
        admin_client.force_login(admin_user)

        vendor_user = User.objects.create_user(email="v@t.com", password="p", role="vendor")
        vendor = VendorProfile.objects.create(
            user=vendor_user, business_name="V", category="photography",
            description="A complete vendor description.", service_area="a", contact_email="e", contact_phone="1",
            status="pending_review"
        )

        changelist_url = reverse("admin:vendors_vendorprofile_changelist")
        data = {
            "action": "reject_selected",
            "_selected_action": [vendor.pk],
            "reason": "Incomplete information"
        }
        response = admin_client.post(changelist_url, data, follow=True)

        vendor.refresh_from_db()
        assert vendor.status == "rejected"
        assert vendor.rejection_reason == "Incomplete information"

    def test_admin_api_cannot_approve_draft_vendor(self, admin_client):
        admin_user = User.objects.create_superuser("admin@t.com", "pass")
        api_client = APIClient()
        api_client.force_authenticate(user=admin_user)

        vendor_user = User.objects.create_user(email="draft@t.com", password="p", role="vendor")
        vendor = VendorProfile.objects.create(
            user=vendor_user, business_name="Draft", category="photography",
            description="d", service_area="a", contact_email="e@example.com", contact_phone="1",
            status="draft"
        )

        response = api_client.post(reverse("admin-vendor-approve", args=[vendor.id]))

        vendor.refresh_from_db()
        assert response.status_code == 400
        assert vendor.status == "draft"

    def test_admin_api_approval_syncs_marketplace_listing(self, admin_client, monkeypatch):
        calls = []
        monkeypatch.setattr(
            "django_app.governance.views.sync_vendor_to_marketplace",
            lambda vendor: calls.append(vendor) or {"status": "ok"},
        )
        admin_user = User.objects.create_superuser("admin@t.com", "pass")
        api_client = APIClient()
        api_client.force_authenticate(user=admin_user)

        vendor_user = User.objects.create_user(email="pending@t.com", password="p", role="vendor")
        vendor = VendorProfile.objects.create(
            user=vendor_user, business_name="Pending", category="photography",
            description="A complete vendor description.", service_area="a", contact_email="e@example.com", contact_phone="1",
            status="pending_review"
        )

        response = api_client.post(reverse("admin-vendor-approve", args=[vendor.id]))

        vendor.refresh_from_db()
        assert response.status_code == 200
        assert vendor.status == "approved"
        assert calls
        assert calls[0].id == vendor.id
        assert calls[0].status == "approved"

    def test_admin_api_lists_vendors_by_status(self, admin_client):
        admin_user = User.objects.create_superuser("admin@t.com", "pass")
        api_client = APIClient()
        api_client.force_authenticate(user=admin_user)

        for status in ["draft", "pending_review", "approved", "rejected", "suspended"]:
            vendor_user = User.objects.create_user(email=f"{status}@t.com", password="p", role="vendor")
            VendorProfile.objects.create(
                user=vendor_user,
                business_name=f"{status} vendor",
                category="photography",
                description="d",
                service_area="a",
                contact_email=f"{status}@example.com",
                contact_phone="1",
                status=status,
            )

        response = api_client.get(reverse("admin-vendors"), {"status": "suspended"})

        assert response.status_code == 200
        assert response.data["count"] == 1
        assert response.data["results"][0]["status"] == "suspended"
        assert response.data["status_counts"]["approved"] == 1

    def test_admin_api_suspend_and_reinstate_vendor_updates_marketplace(self, admin_client, monkeypatch):
        deleted = []
        synced = []
        monkeypatch.setattr(
            "django_app.governance.views.delete_vendor_from_marketplace",
            lambda vendor_id: deleted.append(str(vendor_id)) or {"status": "ok"},
        )
        monkeypatch.setattr(
            "django_app.governance.views.sync_vendor_to_marketplace",
            lambda vendor: synced.append(vendor) or {"status": "ok"},
        )
        admin_user = User.objects.create_superuser("admin@t.com", "pass")
        api_client = APIClient()
        api_client.force_authenticate(user=admin_user)
        vendor_user = User.objects.create_user(email="approved@t.com", password="p", role="vendor")
        vendor = VendorProfile.objects.create(
            user=vendor_user,
            business_name="Approved",
            category="photography",
            description="A complete vendor description.",
            service_area="a",
            contact_email="approved@example.com",
            contact_phone="1",
            status="approved",
        )

        suspend_response = api_client.post(reverse("admin-vendor-suspend", args=[vendor.id]))
        vendor.refresh_from_db()

        assert suspend_response.status_code == 200
        assert vendor.status == "suspended"
        assert deleted == [str(vendor.id)]

        reinstate_response = api_client.post(reverse("admin-vendor-reinstate", args=[vendor.id]))
        vendor.refresh_from_db()

        assert reinstate_response.status_code == 200
        assert vendor.status == "approved"
        assert synced

    def test_admin_package_review_and_hard_delete(self):
        admin_user = User.objects.create_superuser("package-admin@t.com", "pass")
        api_client = APIClient()
        api_client.force_authenticate(user=admin_user)
        vendor_user = User.objects.create_user(email="package-owner@t.com", password="p", role="vendor")
        vendor = VendorProfile.objects.create(
            user=vendor_user,
            business_name="Package Owner",
            category="photography",
            description="A complete vendor description.",
            service_area="a",
            contact_email="owner@example.com",
            contact_phone="1",
            status="approved",
        )
        package = ServicePackage.objects.create(
            vendor=vendor,
            name="Pending Package",
            description="A standard package with enough detail for review.",
            price="25000.00",
            currency="RWF",
            package_tier="standard",
            approval_status=ServicePackage.ApprovalStatus.WAITING_APPROVAL,
            is_active=False,
        )

        pending_response = api_client.get(reverse("admin-vendor-package-pending"))
        approve_response = api_client.post(reverse("admin-vendor-package-approve", args=[package.id]))
        package.refresh_from_db()

        assert pending_response.status_code == 200
        assert pending_response.data["count"] == 1
        assert approve_response.status_code == 200
        assert package.approval_status == ServicePackage.ApprovalStatus.APPROVED
        assert package.is_active is True

        delete_response = api_client.delete(reverse("admin-vendor-package-hard-delete", args=[package.id]))

        assert delete_response.status_code == 200
        assert not ServicePackage.all_objects.filter(id=package.id).exists()

    def test_vendor_cannot_hard_delete_package(self):
        vendor_user = User.objects.create_user(email="not-admin@t.com", password="p", role="vendor")
        api_client = APIClient()
        api_client.force_authenticate(user=vendor_user)
        vendor = VendorProfile.objects.create(
            user=vendor_user,
            business_name="No Hard Delete",
            category="photography",
            description="A complete vendor description.",
            service_area="a",
            contact_email="nohard@example.com",
            contact_phone="1",
            status="approved",
        )
        package = ServicePackage.objects.create(
            vendor=vendor,
            name="Protected Package",
            description="A standard package with enough detail for review.",
            price="25000.00",
            currency="RWF",
            package_tier="standard",
        )

        response = api_client.delete(reverse("admin-vendor-package-hard-delete", args=[package.id]))

        assert response.status_code == 403
        assert ServicePackage.all_objects.filter(id=package.id).exists()

    def test_admin_portfolio_review_and_hard_delete(self):
        admin_user = User.objects.create_superuser("portfolio-admin@t.com", "pass")
        api_client = APIClient()
        api_client.force_authenticate(user=admin_user)
        vendor_user = User.objects.create_user(email="portfolio-owner@t.com", password="p", role="vendor")
        vendor = VendorProfile.objects.create(
            user=vendor_user,
            business_name="Portfolio Owner",
            category="photography",
            description="A complete vendor description.",
            service_area="a",
            contact_email="portfolio@example.com",
            contact_phone="1",
            status="approved",
        )
        media = PortfolioImage.objects.create(
            vendor=vendor,
            media_type=PortfolioImage.MediaType.IMAGE,
            public_id="portfolio/item",
            secure_url="https://example.com/item.jpg",
            upload_status=PortfolioImage.UploadStatus.UPLOADED,
            quality_status=PortfolioImage.QualityStatus.PASSED,
            visibility_status=PortfolioImage.VisibilityStatus.WAITING_APPROVAL,
            is_active=True,
        )

        pending_response = api_client.get(reverse("admin-vendor-portfolio-pending"))
        approve_response = api_client.post(reverse("admin-vendor-portfolio-approve", args=[media.id]))
        media.refresh_from_db()

        assert pending_response.status_code == 200
        assert pending_response.data["count"] == 1
        assert approve_response.status_code == 200
        assert media.visibility_status == PortfolioImage.VisibilityStatus.APPROVED

        delete_response = api_client.delete(reverse("admin-vendor-portfolio-hard-delete", args=[media.id]))

        assert delete_response.status_code == 200
        assert not PortfolioImage.all_objects.filter(id=media.id).exists()

    def test_admin_cannot_approve_failed_portfolio_media(self):
        admin_user = User.objects.create_superuser("portfolio-admin2@t.com", "pass")
        api_client = APIClient()
        api_client.force_authenticate(user=admin_user)
        vendor_user = User.objects.create_user(email="portfolio-failed@t.com", password="p", role="vendor")
        vendor = VendorProfile.objects.create(
            user=vendor_user,
            business_name="Portfolio Failed",
            category="photography",
            description="A complete vendor description.",
            service_area="a",
            contact_email="failed@example.com",
            contact_phone="1",
            status="approved",
        )
        media = PortfolioImage.objects.create(
            vendor=vendor,
            media_type=PortfolioImage.MediaType.IMAGE,
            upload_status=PortfolioImage.UploadStatus.UPLOADED,
            quality_status=PortfolioImage.QualityStatus.FAILED,
            visibility_status=PortfolioImage.VisibilityStatus.PRIVATE,
        )

        response = api_client.post(reverse("admin-vendor-portfolio-approve", args=[media.id]))

        assert response.status_code == 400
        media.refresh_from_db()
        assert media.visibility_status == PortfolioImage.VisibilityStatus.PRIVATE


class TestUserAdminActions:
    def test_ban_user_action(self, admin_client):
        admin_user = User.objects.create_superuser("admin@t.com", "pass")
        admin_client.force_login(admin_user)

        user = User.objects.create_user(
            email="u@t.com",
            password="p",
            first_name="Test",
            last_name="User",
            role="planner",
            is_active=True
        )
        changelist_url = reverse("admin:identity_user_changelist")
        data = {"action": "ban_selected", "_selected_action": [user.pk]}
        response = admin_client.post(changelist_url, data, follow=True)

        user.refresh_from_db()
        assert not user.is_active

    def test_reinstate_user_action(self, admin_client):
        admin_user = User.objects.create_superuser("admin@t.com", "pass")
        admin_client.force_login(admin_user)

        user = User.objects.create_user(
            email="u@t.com",
            password="p",
            first_name="Test",
            last_name="User",
            role="planner",
            is_active=False
        )
        changelist_url = reverse("admin:identity_user_changelist")
        data = {"action": "reinstate_selected", "_selected_action": [user.pk]}
        response = admin_client.post(changelist_url, data, follow=True)

        user.refresh_from_db()
        assert user.is_active
