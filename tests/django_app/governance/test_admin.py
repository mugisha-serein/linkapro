import logging
import uuid
import pytest
from django.test import override_settings
from django.utils import timezone
from django.urls import reverse
from rest_framework.test import APIClient

from django_app.governance.models import AuditLog
from django_app.identity.models import PasswordResetEmailDelivery, User
from django_app.vendors.models import PortfolioImage, ServicePackage, VendorProfile, VerificationDocument

pytestmark = pytest.mark.django_db


class TestVendorApprovalAdmin:
    @override_settings(
        EMAIL_BACKEND="django.core.mail.backends.locmem.EmailBackend",
        DEFAULT_FROM_EMAIL="no-reply@example.test",
        FRONTEND_URL="https://app.example.test",
    )
    def test_admin_email_health_reports_reset_delivery_status(self):
        admin_user = User.objects.create_superuser("email-health-admin@t.com", "pass")
        user = User.objects.create_user(email="reset-health@t.com", password="p", role="planner")
        PasswordResetEmailDelivery.objects.create(
            user=user,
            email_hash="a" * 64,
            email_domain="t.com",
            status=PasswordResetEmailDelivery.Status.SENT,
            sent_at=timezone.now(),
        )
        PasswordResetEmailDelivery.objects.create(
            user=user,
            email_hash="b" * 64,
            email_domain="t.com",
            status=PasswordResetEmailDelivery.Status.FAILED,
            failure_reason="RuntimeError",
            failed_at=timezone.now(),
        )
        api_client = APIClient()
        api_client.force_authenticate(user=admin_user)

        response = api_client.get(reverse("admin-email-health"))

        assert response.status_code == 200
        assert response.data["status"] == "degraded"
        assert response.data["email_backend_configured"] is True
        assert response.data["default_from_email_configured"] is True
        assert response.data["frontend_url_configured"] is True
        assert response.data["recent_password_reset_email_failures"] == 1
        assert response.data["recent_password_reset_email_deferred"] == 0
        assert response.data["last_success_at"]
        assert response.data["last_failure_at"]

    def test_admin_email_health_requires_admin_role(self):
        vendor_user = User.objects.create_user("email-health-vendor@t.com", "pass", role="vendor")
        api_client = APIClient()
        api_client.force_authenticate(user=vendor_user)

        response = api_client.get(reverse("admin-email-health"))

        assert response.status_code == 403

    @override_settings(EMAIL_BACKEND="", DEFAULT_FROM_EMAIL="", FRONTEND_URL="")
    def test_admin_email_health_reports_unhealthy_config(self, caplog):
        admin_user = User.objects.create_superuser("email-health-unhealthy@t.com", "pass")
        api_client = APIClient()
        api_client.force_authenticate(user=admin_user)
        caplog.set_level(logging.ERROR, logger="django_app.governance.views")

        response = api_client.get(reverse("admin-email-health"))

        assert response.status_code == 200
        assert response.data["status"] == "unhealthy"
        assert response.data["email_backend_configured"] is False
        assert response.data["default_from_email_configured"] is False
        assert response.data["frontend_url_configured"] is False
        assert "email_health_unhealthy" in caplog.text

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

    @pytest.mark.parametrize("vendor_status", ["draft", "pending_review", "approved", "rejected", "suspended"])
    def test_admin_api_vendor_detail_returns_all_vendor_statuses(self, vendor_status):
        admin_user = User.objects.create_superuser(f"detail-admin-{vendor_status}@t.com", "pass")
        api_client = APIClient()
        api_client.force_authenticate(user=admin_user)
        vendor_user = User.objects.create_user(
            email=f"detail-{vendor_status}@t.com",
            password="p",
            role="vendor",
            first_name="Vendor",
            last_name=vendor_status.title(),
        )
        vendor = VendorProfile.objects.create(
            user=vendor_user,
            business_name=f"{vendor_status} vendor",
            category="photography",
            description="A complete vendor description.",
            service_area="Kigali",
            contact_email=f"{vendor_status}@example.com",
            contact_phone="1",
            status=vendor_status,
        )
        ServicePackage.objects.create(
            vendor=vendor,
            name="Review Package",
            description="A standard package with enough detail for review.",
            price="25000.00",
            currency="RWF",
            package_tier="standard",
        )
        PortfolioImage.objects.create(vendor=vendor, media_type=PortfolioImage.MediaType.IMAGE)

        response = api_client.get(reverse("admin-vendor-detail", args=[vendor.id]))

        assert response.status_code == 200
        assert response.data["success"] is True
        assert response.data["code"] == "admin_vendor_detail_loaded"
        detail = response.data["data"]
        assert detail["profile"]["id"] == str(vendor.id)
        assert detail["profile"]["status"] == vendor_status
        assert detail["user"]["email"] == vendor_user.email
        assert detail["review_context"]["packages_count"] == 1
        assert detail["review_context"]["portfolio_count"] == 1

    def test_admin_api_vendor_detail_requires_admin_role(self):
        vendor_user = User.objects.create_user(email="detail-vendor@t.com", password="p", role="vendor")
        vendor = VendorProfile.objects.create(
            user=vendor_user,
            business_name="Private detail",
            category="photography",
            description="A complete vendor description.",
            service_area="Kigali",
            contact_email="detail@example.com",
            contact_phone="1",
            status="pending_review",
        )
        api_client = APIClient()
        api_client.force_authenticate(user=vendor_user)

        response = api_client.get(reverse("admin-vendor-detail", args=[vendor.id]))

        assert response.status_code == 403

    def test_pending_vendor_public_profile_404_but_admin_detail_visible(self):
        admin_user = User.objects.create_superuser("public-admin@t.com", "pass")
        vendor_user = User.objects.create_user(email="public-pending@t.com", password="p", role="vendor")
        vendor = VendorProfile.objects.create(
            user=vendor_user,
            business_name="Pending public",
            category="photography",
            description="A complete vendor description.",
            service_area="Kigali",
            contact_email="pending-public@example.com",
            contact_phone="1",
            status="pending_review",
        )
        public_client = APIClient()
        admin_client = APIClient()
        admin_client.force_authenticate(user=admin_user)

        public_response = public_client.get(reverse("public-vendor-profile", args=[vendor.id]))
        admin_response = admin_client.get(reverse("admin-vendor-detail", args=[vendor.id]))

        assert public_response.status_code == 404
        assert admin_response.status_code == 200
        assert admin_response.data["data"]["profile"]["status"] == "pending_review"

    def test_admin_api_vendor_detail_returns_full_review_payload(self):
        admin_user = User.objects.create_superuser("full-detail-admin@t.com", "pass")
        api_client = APIClient()
        api_client.force_authenticate(user=admin_user)
        vendor_user = User.objects.create_user(
            email="full-detail-vendor@t.com",
            password="p",
            role="vendor",
            first_name="Full",
            last_name="Vendor",
        )
        vendor = VendorProfile.objects.create(
            user=vendor_user,
            business_name="Full Detail Vendor",
            category="other",
            custom_category="Lighting",
            description="A complete vendor description.",
            service_area="Kigali",
            contact_email="full-detail@example.com",
            contact_phone="1",
            website="https://vendor.example.test",
            profile_image_url="https://cdn.example.test/profile.jpg",
            cover_image_url="https://cdn.example.test/cover.jpg",
            status="pending_review",
            submitted_at=timezone.now(),
        )
        approved_at = timezone.now()
        package = ServicePackage.objects.create(
            vendor=vendor,
            name="Review Package",
            description="A standard package with enough detail for review.",
            price="25000.00",
            currency="RWF",
            package_tier="standard",
            approval_status=ServicePackage.ApprovalStatus.APPROVED,
            last_approved_at=approved_at,
            next_vendor_edit_allowed_at=approved_at + ServicePackage.vendor_edit_cooldown_delta(),
        )
        media = PortfolioImage.objects.create(
            vendor=vendor,
            media_type=PortfolioImage.MediaType.IMAGE,
            secure_url="https://cdn.example.test/portfolio.jpg",
            cloudinary_secure_url="https://res.cloudinary.com/example/portfolio.jpg",
            local_preview_url="https://preview.example.test/portfolio.jpg",
            caption="Portfolio caption",
            upload_status=PortfolioImage.UploadStatus.UPLOADED,
            quality_status=PortfolioImage.QualityStatus.NEEDS_MANUAL_REVIEW,
            visibility_status=PortfolioImage.VisibilityStatus.WAITING_APPROVAL,
            analyzer_score=72,
            analyzer_summary="Needs a human look.",
            width=1200,
            height=800,
        )
        document = VerificationDocument.objects.create(
            vendor=vendor,
            document_type=VerificationDocument.DocumentType.BUSINESS_REGISTRATION,
            original_filename="registration.pdf",
            secure_url="https://docs.example.test/registration.pdf",
            cloudinary_secure_url="https://res.cloudinary.com/example/registration.pdf",
            mime_type="application/pdf",
            file_size=2048,
            upload_status=VerificationDocument.UploadStatus.COMPLETED,
            verification_status=VerificationDocument.VerificationStatus.VERIFIED,
            fraud_status=VerificationDocument.FraudStatus.REVIEW_REQUIRED,
            fraud_score=42,
            fraud_reasons=["name_mismatch"],
            odcr_status="completed",
            odcr_score=91,
            odcr_result_summary="Business registration detected.",
        )
        AuditLog.objects.create(
            admin=admin_user,
            action_type=AuditLog.ActionType.APPROVE_PACKAGE,
            target_type="service_package",
            target_id=package.id,
            details={"package": "approved"},
        )
        AuditLog.objects.create(
            admin=admin_user,
            action_type=AuditLog.ActionType.APPROVE_PORTFOLIO_MEDIA,
            target_type="portfolio_image",
            target_id=media.id,
            details={"media": "approved"},
        )
        AuditLog.objects.create(
            admin=admin_user,
            action_type=AuditLog.ActionType.REJECT_VENDOR,
            target_type="vendor_profile",
            target_id=vendor.id,
            details={"reason": "test"},
        )

        response = api_client.get(reverse("admin-vendor-detail", args=[vendor.id]))

        assert response.status_code == 200
        assert response.data["success"] is True
        assert response.data["code"] == "admin_vendor_detail_loaded"
        detail = response.data["data"]
        assert set(detail) == {
            "profile",
            "user",
            "packages",
            "portfolio",
            "verification_documents",
            "review_context",
            "available_actions",
            "audit_logs",
        }
        assert detail["profile"]["custom_category"] == "Lighting"
        assert detail["profile"]["profile_image_url"] == "https://cdn.example.test/profile.jpg"
        assert detail["user"]["id"] == str(vendor_user.id)
        assert detail["user"]["email"] == vendor_user.email
        assert detail["packages"][0]["id"] == str(package.id)
        assert detail["packages"][0]["approval_status"] == ServicePackage.ApprovalStatus.APPROVED
        assert detail["packages"][0]["last_approved_at"] == package.last_approved_at.isoformat()
        assert detail["packages"][0]["next_vendor_edit_allowed_at"] == package.next_vendor_edit_allowed_at.isoformat()
        assert detail["packages"][0]["can_edit_now"] is False
        assert detail["portfolio"][0]["id"] == str(media.id)
        assert detail["portfolio"][0]["visibility_status"] == PortfolioImage.VisibilityStatus.WAITING_APPROVAL
        assert detail["portfolio"][0]["quality_status"] == PortfolioImage.QualityStatus.NEEDS_MANUAL_REVIEW
        assert detail["portfolio"][0]["display_url"] == media.cloudinary_secure_url
        assert detail["portfolio"][0]["width"] == 1200
        assert detail["verification_documents"][0]["id"] == str(document.id)
        assert detail["verification_documents"][0]["fraud_status"] == VerificationDocument.FraudStatus.REVIEW_REQUIRED
        assert detail["verification_documents"][0]["fraud_reasons"] == ["name_mismatch"]
        assert detail["verification_documents"][0]["odcr_result_summary"] == "Business registration detected."
        assert detail["review_context"] == {
            "packages_count": 1,
            "pending_packages_count": 0,
            "approved_packages_count": 1,
            "rejected_packages_count": 0,
            "portfolio_count": 1,
            "pending_portfolio_count": 1,
            "approved_portfolio_count": 0,
            "rejected_portfolio_count": 0,
            "verification_documents_count": 1,
            "verified_documents_count": 1,
            "failed_documents_count": 0,
        }
        assert detail["available_actions"] == {
            "approve_vendor": True,
            "reject_vendor": True,
            "suspend_vendor": False,
            "reinstate_vendor": False,
            "ban_user": True,
            "reinstate_user": False,
        }
        assert {log["target_type"] for log in detail["audit_logs"]} == {
            "vendor_profile",
            "portfolio_image",
            "service_package",
        }
        assert detail["audit_logs"][0]["admin"]["email"] == admin_user.email

    @pytest.mark.parametrize(
        ("vendor_status", "is_active", "expected_actions"),
        [
            (
                "pending_review",
                True,
                {
                    "approve_vendor": True,
                    "reject_vendor": True,
                    "suspend_vendor": False,
                    "reinstate_vendor": False,
                    "ban_user": True,
                    "reinstate_user": False,
                },
            ),
            (
                "approved",
                True,
                {
                    "approve_vendor": False,
                    "reject_vendor": False,
                    "suspend_vendor": True,
                    "reinstate_vendor": False,
                    "ban_user": True,
                    "reinstate_user": False,
                },
            ),
            (
                "suspended",
                False,
                {
                    "approve_vendor": False,
                    "reject_vendor": False,
                    "suspend_vendor": False,
                    "reinstate_vendor": True,
                    "ban_user": False,
                    "reinstate_user": True,
                },
            ),
        ],
    )
    def test_admin_api_vendor_detail_available_actions_match_status(
        self,
        vendor_status,
        is_active,
        expected_actions,
    ):
        admin_user = User.objects.create_superuser(f"actions-admin-{vendor_status}@t.com", "pass")
        api_client = APIClient()
        api_client.force_authenticate(user=admin_user)
        vendor_user = User.objects.create_user(
            email=f"actions-vendor-{vendor_status}@t.com",
            password="p",
            role="vendor",
            is_active=is_active,
        )
        vendor = VendorProfile.objects.create(
            user=vendor_user,
            business_name=f"{vendor_status} actions",
            category="photography",
            description="A complete vendor description.",
            service_area="Kigali",
            contact_email=f"{vendor_status}-actions@example.com",
            contact_phone="1",
            status=vendor_status,
        )

        response = api_client.get(reverse("admin-vendor-detail", args=[vendor.id]))

        assert response.status_code == 200
        assert response.data["data"]["available_actions"] == expected_actions

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

    def test_admin_vendor_reject_without_reason_uses_generated_policy_reason(self):
        admin_user = User.objects.create_superuser("policy-reject-admin@t.com", "pass")
        api_client = APIClient()
        api_client.force_authenticate(user=admin_user)
        vendor_user = User.objects.create_user(email="policy-reject-vendor@t.com", password="p", role="vendor")
        vendor = VendorProfile.objects.create(
            user=vendor_user,
            business_name="Policy Reject",
            category="photography",
            description="A complete vendor description.",
            service_area="Kigali",
            contact_email="policy-reject@example.com",
            contact_phone="1",
            status="pending_review",
        )

        response = api_client.post(reverse("admin-vendor-reject", args=[vendor.id]))

        vendor.refresh_from_db()
        audit = AuditLog.objects.get(action_type=AuditLog.ActionType.REJECT_VENDOR, target_id=vendor.id)
        assert response.status_code == 200
        assert response.data["reason"]["source"] == "system"
        assert response.data["reason"]["policy_code"] == "vendor_profile_reject"
        assert vendor.rejection_reason == response.data["reason"]["reason"]
        assert audit.details["reason"] == response.data["reason"]["reason"]
        assert audit.details["reason_source"] == "system"
        assert audit.details["community_guideline"]

    def test_admin_vendor_reject_with_reason_uses_admin_policy_reason(self):
        admin_user = User.objects.create_superuser("policy-admin-reason@t.com", "pass")
        api_client = APIClient()
        api_client.force_authenticate(user=admin_user)
        vendor_user = User.objects.create_user(email="policy-admin-reason-vendor@t.com", password="p", role="vendor")
        vendor = VendorProfile.objects.create(
            user=vendor_user,
            business_name="Policy Admin Reason",
            category="photography",
            description="A complete vendor description.",
            service_area="Kigali",
            contact_email="policy-admin-reason@example.com",
            contact_phone="1",
            status="pending_review",
        )

        response = api_client.post(
            reverse("admin-vendor-reject", args=[vendor.id]),
            {"reason": "Business registration number could not be verified."},
            format="json",
        )

        vendor.refresh_from_db()
        audit = AuditLog.objects.get(action_type=AuditLog.ActionType.REJECT_VENDOR, target_id=vendor.id)
        assert response.status_code == 200
        assert response.data["reason"]["source"] == "admin"
        assert response.data["reason"]["reason"] == "Business registration number could not be verified."
        assert vendor.rejection_reason == "Business registration number could not be verified."
        assert audit.details["reason_source"] == "admin"
        assert audit.details["policy_code"] == "vendor_profile_reject"

    def test_admin_vendor_suspend_and_reinstate_return_generated_policy_reasons(self, monkeypatch):
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
        admin_user = User.objects.create_superuser("policy-status-admin@t.com", "pass")
        api_client = APIClient()
        api_client.force_authenticate(user=admin_user)
        vendor_user = User.objects.create_user(email="policy-status-vendor@t.com", password="p", role="vendor")
        vendor = VendorProfile.objects.create(
            user=vendor_user,
            business_name="Policy Status",
            category="photography",
            description="A complete vendor description.",
            service_area="Kigali",
            contact_email="policy-status@example.com",
            contact_phone="1",
            status="approved",
        )

        suspend_response = api_client.post(reverse("admin-vendor-suspend", args=[vendor.id]))
        vendor.refresh_from_db()
        reinstate_response = api_client.post(reverse("admin-vendor-reinstate", args=[vendor.id]))
        vendor.refresh_from_db()

        suspend_audit = AuditLog.objects.get(action_type=AuditLog.ActionType.SUSPEND_VENDOR, target_id=vendor.id)
        reinstate_audit = AuditLog.objects.get(
            action_type=AuditLog.ActionType.APPROVE_VENDOR,
            target_id=vendor.id,
            details__from="suspended",
        )
        assert suspend_response.status_code == 200
        assert suspend_response.data["reason"]["policy_code"] == "vendor_profile_suspend"
        assert suspend_audit.details["reason_source"] == "system"
        assert reinstate_response.status_code == 200
        assert reinstate_response.data["reason"]["policy_code"] == "vendor_profile_reinstate"
        assert reinstate_audit.details["reason_source"] == "system"
        assert vendor.status == "approved"
        assert deleted == [str(vendor.id)]
        assert synced

    def test_admin_user_ban_and_reinstate_return_generated_policy_reasons(self):
        admin_user = User.objects.create_superuser("policy-user-admin@t.com", "pass")
        target_user = User.objects.create_user(email="policy-user@t.com", password="p", role="planner")
        api_client = APIClient()
        api_client.force_authenticate(user=admin_user)

        ban_response = api_client.post(reverse("admin-user-ban", args=[target_user.id]))
        target_user.refresh_from_db()
        reinstate_response = api_client.post(reverse("admin-user-reinstate", args=[target_user.id]))
        target_user.refresh_from_db()

        ban_audit = AuditLog.objects.get(action_type=AuditLog.ActionType.BAN_USER, target_id=target_user.id)
        reinstate_audit = AuditLog.objects.get(
            action_type=AuditLog.ActionType.REINSTATE_USER,
            target_id=target_user.id,
        )
        assert ban_response.status_code == 200
        assert ban_response.data["reason"]["policy_code"] == "user_account_ban"
        assert ban_response.data["email"] == target_user.email
        assert ban_audit.details["reason_source"] == "system"
        assert reinstate_response.status_code == 200
        assert reinstate_response.data["reason"]["policy_code"] == "user_account_reinstate"
        assert reinstate_response.data["email"] == target_user.email
        assert reinstate_audit.details["reason_source"] == "system"
        assert target_user.is_active is True

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

    def test_admin_package_reject_and_hard_delete_use_policy_reasons(self):
        admin_user = User.objects.create_superuser("policy-package-admin@t.com", "pass")
        api_client = APIClient()
        api_client.force_authenticate(user=admin_user)
        vendor_user = User.objects.create_user(email="policy-package-owner@t.com", password="p", role="vendor")
        vendor = VendorProfile.objects.create(
            user=vendor_user,
            business_name="Policy Package Owner",
            category="photography",
            description="A complete vendor description.",
            service_area="Kigali",
            contact_email="policy-package@example.com",
            contact_phone="1",
            status="approved",
        )
        rejected_package = ServicePackage.objects.create(
            vendor=vendor,
            name="Package To Reject",
            description="A standard package with enough detail for review.",
            price="25000.00",
            currency="RWF",
            package_tier="standard",
            approval_status=ServicePackage.ApprovalStatus.WAITING_APPROVAL,
        )
        deleted_package = ServicePackage.objects.create(
            vendor=vendor,
            name="Package To Delete",
            description="A standard package with enough detail for review.",
            price="30000.00",
            currency="RWF",
            package_tier="standard",
        )

        reject_response = api_client.post(reverse("admin-vendor-package-reject", args=[rejected_package.id]))
        delete_response = api_client.delete(reverse("admin-vendor-package-hard-delete", args=[deleted_package.id]))

        rejected_package.refresh_from_db()
        reject_audit = AuditLog.objects.get(
            action_type=AuditLog.ActionType.REJECT_PACKAGE,
            target_id=rejected_package.id,
        )
        delete_audit = AuditLog.objects.get(
            action_type=AuditLog.ActionType.HARD_DELETE_PACKAGE,
            target_id=deleted_package.id,
        )
        assert reject_response.status_code == 200
        assert reject_response.data["reason"]["policy_code"] == "service_package_reject"
        assert reject_response.data["reason"]["source"] == "system"
        assert rejected_package.rejection_reason == reject_response.data["reason"]["reason"]
        assert reject_audit.details["policy_code"] == "service_package_reject"
        assert delete_response.status_code == 200
        assert delete_response.data["reason"]["policy_code"] == "service_package_hard_delete"
        assert delete_audit.details["reason_source"] == "system"

    def test_admin_package_approve_logs_policy_reason(self):
        admin_user = User.objects.create_superuser("policy-package-approve-admin@t.com", "pass")
        api_client = APIClient()
        api_client.force_authenticate(user=admin_user)
        vendor_user = User.objects.create_user(email="policy-package-approve-owner@t.com", password="p", role="vendor")
        vendor = VendorProfile.objects.create(
            user=vendor_user,
            business_name="Policy Package Approve Owner",
            category="photography",
            description="A complete vendor description.",
            service_area="Kigali",
            contact_email="policy-package-approve@example.com",
            contact_phone="1",
            status="approved",
        )
        package = ServicePackage.objects.create(
            vendor=vendor,
            name="Package To Approve",
            description="A standard package with enough detail for review.",
            price="30000.00",
            currency="RWF",
            package_tier="standard",
            approval_status=ServicePackage.ApprovalStatus.WAITING_APPROVAL,
        )

        response = api_client.post(reverse("admin-vendor-package-approve", args=[package.id]))

        audit = AuditLog.objects.get(action_type=AuditLog.ActionType.APPROVE_PACKAGE, target_id=package.id)
        assert response.status_code == 200
        assert response.data["reason"]["policy_code"] == "service_package_approve"
        assert response.data["package"]["approval_status"] == ServicePackage.ApprovalStatus.APPROVED
        assert audit.details["reason_source"] == "system"

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

    def test_admin_portfolio_reject_and_hard_delete_use_policy_reasons(self):
        admin_user = User.objects.create_superuser("policy-portfolio-admin@t.com", "pass")
        api_client = APIClient()
        api_client.force_authenticate(user=admin_user)
        vendor_user = User.objects.create_user(email="policy-portfolio-owner@t.com", password="p", role="vendor")
        vendor = VendorProfile.objects.create(
            user=vendor_user,
            business_name="Policy Portfolio Owner",
            category="photography",
            description="A complete vendor description.",
            service_area="Kigali",
            contact_email="policy-portfolio@example.com",
            contact_phone="1",
            status="approved",
        )
        rejected_media = PortfolioImage.objects.create(
            vendor=vendor,
            media_type=PortfolioImage.MediaType.IMAGE,
            upload_status=PortfolioImage.UploadStatus.UPLOADED,
            quality_status=PortfolioImage.QualityStatus.PASSED,
            visibility_status=PortfolioImage.VisibilityStatus.WAITING_APPROVAL,
        )
        deleted_media = PortfolioImage.objects.create(
            vendor=vendor,
            media_type=PortfolioImage.MediaType.IMAGE,
            upload_status=PortfolioImage.UploadStatus.UPLOADED,
            quality_status=PortfolioImage.QualityStatus.PASSED,
            visibility_status=PortfolioImage.VisibilityStatus.WAITING_APPROVAL,
        )

        reject_response = api_client.post(reverse("admin-vendor-portfolio-reject", args=[rejected_media.id]))
        delete_response = api_client.delete(reverse("admin-vendor-portfolio-hard-delete", args=[deleted_media.id]))

        rejected_media.refresh_from_db()
        reject_audit = AuditLog.objects.get(
            action_type=AuditLog.ActionType.REJECT_PORTFOLIO_MEDIA,
            target_id=rejected_media.id,
        )
        delete_audit = AuditLog.objects.get(
            action_type=AuditLog.ActionType.HARD_DELETE_PORTFOLIO_MEDIA,
            target_id=deleted_media.id,
        )
        assert reject_response.status_code == 200
        assert reject_response.data["reason"]["policy_code"] == "portfolio_media_reject"
        assert rejected_media.rejection_reason == reject_response.data["reason"]["reason"]
        assert reject_audit.details["reason_source"] == "system"
        assert delete_response.status_code == 200
        assert delete_response.data["reason"]["policy_code"] == "portfolio_media_hard_delete"
        assert delete_audit.details["policy_code"] == "portfolio_media_hard_delete"

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
