import uuid
import pytest
from django.urls import reverse
from django.test import Client

from django_app.identity.models import User
from django_app.vendors.models import VendorProfile

pytestmark = pytest.mark.django_db


class TestVendorApprovalAdmin:
    def test_approve_vendor_action(self, admin_client):
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

    def test_reject_vendor_action(self, admin_client):
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