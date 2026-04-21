import uuid
import pytest
from datetime import date

from domain.governance.entities import (
    AuditLog as DomainLog, ContentFlag as DomainFlag, PlatformMetric as DomainMetric,
    AdminActionType, FlagStatus, ContentType
)
from infrastructure.repos.django_audit_log_repository import DjangoAuditLogRepository
from infrastructure.repos.django_content_flag_repository import DjangoContentFlagRepository
from infrastructure.repos.django_platform_metric_repository import DjangoPlatformMetricRepository
from django_app.identity.models import User
from django_app.vendors.models import VendorProfile

pytestmark = pytest.mark.django_db


class TestDjangoAuditLogRepository:
    def test_save_and_list_by_admin(self):
        admin = User.objects.create_superuser("admin@t.com", "pass")
        repo = DjangoAuditLogRepository()
        log = DomainLog(
            id=uuid.uuid4(),
            admin_id=admin.id,
            action_type=AdminActionType.APPROVE_VENDOR,
            target_type="vendor",
            target_id=uuid.uuid4(),
        )
        repo.save(log)
        logs = repo.list_by_admin(admin.id)
        assert len(logs) == 1
        assert logs[0].action_type == AdminActionType.APPROVE_VENDOR


class TestDjangoContentFlagRepository:
    def test_save_and_list_pending(self):
        user = User.objects.create_user(email="r@t.com", password="p")
        repo = DjangoContentFlagRepository()
        flag = DomainFlag(
            id=uuid.uuid4(),
            reported_by=user.id,
            content_type=ContentType.VENDOR_PROFILE,
            content_id=uuid.uuid4(),
            reason="Test",
        )
        repo.save(flag)
        pending = repo.list_pending()
        assert len(pending) == 1
        assert pending[0].status == FlagStatus.PENDING

    def test_mark_reviewed_updates_status(self):
        user = User.objects.create_user(email="r@t.com", password="p")
        repo = DjangoContentFlagRepository()
        flag = DomainFlag(
            id=uuid.uuid4(),
            reported_by=user.id,
            content_type=ContentType.REVIEW,
            content_id=uuid.uuid4(),
            reason="Test",
        )
        saved = repo.save(flag)
        saved.mark_reviewed("Done")
        repo.save(saved)
        retrieved = repo.get_by_id(saved.id)
        assert retrieved.status == FlagStatus.REVIEWED
        assert retrieved.admin_notes == "Done"


class TestDjangoPlatformMetricRepository:
    def test_save_and_get_latest(self):
        repo = DjangoPlatformMetricRepository()
        metric = DomainMetric(date=date.today(), total_users=10)
        repo.save(metric)
        latest = repo.get_latest()
        assert latest.total_users == 10

    def test_generate_current_metrics(self):
        # Create some test data
        User.objects.create_user(email="p1@t.com", password="p", role="planner")
        User.objects.create_user(email="v1@t.com", password="p", role="vendor")
        vendor_user = User.objects.create_user(email="v2@t.com", password="p", role="vendor")
        VendorProfile.objects.create(
            user=vendor_user, business_name="V", category="photography",
            description="d", service_area="a", contact_email="e", contact_phone="1",
            status="approved"
        )
        repo = DjangoPlatformMetricRepository()
        metric = repo.generate_current_metrics()
        assert metric.total_users == 3
        assert metric.total_planners == 1
        assert metric.total_vendors == 2
        assert metric.active_vendors == 1