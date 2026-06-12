import uuid
import pytest
from django.urls import reverse
from rest_framework.test import APIClient

from django_app.identity.models import User
from django_app.vendors.models import VendorProfile

pytestmark = pytest.mark.django_db


class TestVendorApprovalAdmin:
    def test_approve_vendor_action(self, admin_client, monkeypatch):
        monkeypatch.setattr(
            "tasks.marketplace_sync.sync_vendor_listing_to_fastapi",
            lambda *args, **kwargs: {"status": "ok"},
        )
        admin_user = User.objects.create_superuser("admin@t.com", "pass")
        admin_client.force_login(admin_user)

        vendor_user = User.objects.create_user(email="v@t.com", password="p", role="vendor")
        vendor = VendorProfile.objects.create(
            user=vendor_user, business_name="V", category="photography",
            description="d", service_area="a", contact_email="e", contact_phone="1",
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
            "tasks.marketplace_sync.delete_vendor_listing_from_fastapi",
            lambda *args, **kwargs: {"status": "ok"},
        )
        admin_user = User.objects.create_superuser("admin@t.com", "pass")
        admin_client.force_login(admin_user)

        vendor_user = User.objects.create_user(email="v@t.com", password="p", role="vendor")
        vendor = VendorProfile.objects.create(
            user=vendor_user, business_name="V", category="photography",
            description="d", service_area="a", contact_email="e", contact_phone="1",
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
            "tasks.marketplace_sync.sync_vendor_listing_to_fastapi",
            lambda *args, **kwargs: calls.append((args, kwargs)) or {"status": "ok"},
        )
        admin_user = User.objects.create_superuser("admin@t.com", "pass")
        api_client = APIClient()
        api_client.force_authenticate(user=admin_user)

        vendor_user = User.objects.create_user(email="pending@t.com", password="p", role="vendor")
        vendor = VendorProfile.objects.create(
            user=vendor_user, business_name="Pending", category="photography",
            description="d", service_area="a", contact_email="e@example.com", contact_phone="1",
            status="pending_review"
        )

        response = api_client.post(reverse("admin-vendor-approve", args=[vendor.id]))

        vendor.refresh_from_db()
        assert response.status_code == 200
        assert vendor.status == "approved"
        assert calls
        assert calls[0][0][0] == str(vendor.id)
        assert calls[0][0][-1] == "approved"

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
            "tasks.marketplace_sync.delete_vendor_listing_from_fastapi",
            lambda vendor_id: deleted.append(vendor_id) or {"status": "ok"},
        )
        monkeypatch.setattr(
            "tasks.marketplace_sync.sync_vendor_listing_to_fastapi",
            lambda *args, **kwargs: synced.append((args, kwargs)) or {"status": "ok"},
        )
        admin_user = User.objects.create_superuser("admin@t.com", "pass")
        api_client = APIClient()
        api_client.force_authenticate(user=admin_user)
        vendor_user = User.objects.create_user(email="approved@t.com", password="p", role="vendor")
        vendor = VendorProfile.objects.create(
            user=vendor_user,
            business_name="Approved",
            category="photography",
            description="d",
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
