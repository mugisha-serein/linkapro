import uuid
import pytest
from datetime import datetime, date
from freezegun import freeze_time

from domain.governance.entities import (
    AuditLog, ContentFlag, PlatformMetric,
    AdminActionType, FlagStatus, ContentType
)
from domain.shared.utils import utc_now


class TestAuditLog:
    def test_create_audit_log(self):
        log = AuditLog(
            id=uuid.uuid4(),
            admin_id=uuid.uuid4(),
            action_type=AdminActionType.APPROVE_VENDOR,
            target_type="vendor",
            target_id=uuid.uuid4(),
            details={"reason": "Approved after review"}
        )
        assert log.action_type == AdminActionType.APPROVE_VENDOR
        assert log.details["reason"] == "Approved after review"


class TestContentFlag:
    def test_create_flag_defaults(self):
        flag = ContentFlag(
            id=uuid.uuid4(),
            reported_by=uuid.uuid4(),
            content_type=ContentType.VENDOR_PROFILE,
            content_id=uuid.uuid4(),
            reason="Inappropriate content"
        )
        assert flag.status == FlagStatus.PENDING
        assert flag.admin_notes is None

    def test_mark_reviewed(self):
        flag = ContentFlag(
            id=uuid.uuid4(),
            reported_by=uuid.uuid4(),
            content_type=ContentType.REVIEW,
            content_id=uuid.uuid4(),
            reason="Spam"
        )
        frozen = datetime(2025, 1, 1, 12, 0, 0, tzinfo=utc_now().tzinfo)
        with freeze_time(frozen):
            flag.mark_reviewed("Removed the review")
        assert flag.status == FlagStatus.REVIEWED
        assert flag.admin_notes == "Removed the review"
        assert flag.updated_at == frozen

    def test_dismiss(self):
        flag = ContentFlag(
            id=uuid.uuid4(),
            reported_by=uuid.uuid4(),
            content_type=ContentType.PORTFOLIO_IMAGE,
            content_id=uuid.uuid4(),
            reason="Not inappropriate"
        )
        frozen = datetime(2025, 1, 1, tzinfo=utc_now().tzinfo)
        with freeze_time(frozen):
            flag.dismiss("No violation")
        assert flag.status == FlagStatus.DISMISSED
        assert flag.admin_notes == "No violation"
        assert flag.updated_at == frozen


class TestPlatformMetric:
    def test_create_metric(self):
        metric = PlatformMetric(
            date=date(2025, 1, 1),
            total_users=100,
            total_planners=60,
            total_vendors=40,
            active_vendors=35,
            pending_vendor_approvals=5,
            total_events=20,
            total_inquiries=150,
            total_reviews=45
        )
        assert metric.total_users == 100
        assert metric.pending_vendor_approvals == 5