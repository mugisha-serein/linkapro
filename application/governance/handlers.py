import uuid
from typing import List, Optional

from domain.shared.utils import utc_now
from domain.governance.entities import (
    AuditLog, ContentFlag, PlatformMetric,
    AdminActionType, FlagStatus, ContentType
)
from domain.governance.interfaces import (
    IAuditLogRepository, IContentFlagRepository, IPlatformMetricRepository
)
from domain.governance.events import AdminActionPerformed

from domain.vendors.interfaces import IVendorProfileRepository
from domain.identity.interfaces import IUserRepository

from .commands import *
from .dtos import *


class GovernanceCommandHandlers:
    def __init__(
        self,
        audit_repo: IAuditLogRepository,
        flag_repo: IContentFlagRepository,
        metric_repo: IPlatformMetricRepository,
        vendor_repo: IVendorProfileRepository,
        user_repo: IUserRepository,
        event_dispatcher,
    ):
        self.audit_repo = audit_repo
        self.flag_repo = flag_repo
        self.metric_repo = metric_repo
        self.vendor_repo = vendor_repo
        self.user_repo = user_repo
        self.event_dispatcher = event_dispatcher

    def approve_vendor(self, cmd: ApproveVendorCommand) -> None:
        vendor = self.vendor_repo.get_by_id(cmd.vendor_id)
        if not vendor:
            raise ValueError("Vendor not found")
        vendor.approve()
        self.vendor_repo.save(vendor)
        self._log_action(cmd.admin_id, AdminActionType.APPROVE_VENDOR, "vendor", cmd.vendor_id)

    def reject_vendor(self, cmd: RejectVendorCommand) -> None:
        vendor = self.vendor_repo.get_by_id(cmd.vendor_id)
        if not vendor:
            raise ValueError("Vendor not found")
        vendor.reject(cmd.reason)
        self.vendor_repo.save(vendor)
        self._log_action(cmd.admin_id, AdminActionType.REJECT_VENDOR, "vendor", cmd.vendor_id,
                         {"reason": cmd.reason})

    def suspend_vendor(self, cmd: SuspendVendorCommand) -> None:
        vendor = self.vendor_repo.get_by_id(cmd.vendor_id)
        if not vendor:
            raise ValueError("Vendor not found")
        vendor.suspend()
        self.vendor_repo.save(vendor)
        self._log_action(cmd.admin_id, AdminActionType.SUSPEND_VENDOR, "vendor", cmd.vendor_id)

    def ban_user(self, cmd: BanUserCommand) -> None:
        user = self.user_repo.get_by_id(cmd.user_id)
        if not user:
            raise ValueError("User not found")
        user.deactivate()
        self.user_repo.save(user)
        self._log_action(cmd.admin_id, AdminActionType.BAN_USER, "user", cmd.user_id)

    def suspend_user(self, cmd: SuspendUserCommand) -> None:
        user = self.user_repo.get_by_id(cmd.user_id)
        if not user:
            raise ValueError("User not found")
        user.deactivate()  # same effect as ban, could have separate status
        self.user_repo.save(user)
        self._log_action(cmd.admin_id, AdminActionType.SUSPEND_USER, "user", cmd.user_id)

    def reinstate_user(self, cmd: ReinstateUserCommand) -> None:
        user = self.user_repo.get_by_id(cmd.user_id)
        if not user:
            raise ValueError("User not found")
        user.activate()
        self.user_repo.save(user)
        self._log_action(cmd.admin_id, AdminActionType.REINSTATE_USER, "user", cmd.user_id)

    def flag_content(self, cmd: FlagContentCommand) -> ContentFlagDTO:
        flag = ContentFlag(
            id=uuid.uuid4(),
            reported_by=cmd.reported_by,
            content_type=ContentType(cmd.content_type),
            content_id=cmd.content_id,
            reason=cmd.reason,
        )
        saved = self.flag_repo.save(flag)
        return self._to_flag_dto(saved)

    def resolve_flag(self, cmd: ResolveFlagCommand) -> ContentFlagDTO:
        flag = self.flag_repo.get_by_id(cmd.flag_id)
        if not flag:
            raise ValueError("Flag not found")
        if cmd.dismiss:
            flag.dismiss(cmd.notes)
        else:
            flag.mark_reviewed(cmd.notes)
        saved = self.flag_repo.save(flag)
        self._log_action(cmd.admin_id, AdminActionType.FLAG_RESOLVE, "content_flag", cmd.flag_id,
                         {"dismiss": cmd.dismiss})
        return self._to_flag_dto(saved)

    def generate_metrics(self, cmd: GenerateMetricsCommand) -> PlatformMetricDTO:
        metric = self.metric_repo.generate_current_metrics()
        saved = self.metric_repo.save(metric)
        return self._to_metric_dto(saved)

    def _log_action(self, admin_id: uuid.UUID, action_type: AdminActionType,
                    target_type: str, target_id: uuid.UUID, details: dict = None):
        log = AuditLog(
            id=uuid.uuid4(),
            admin_id=admin_id,
            action_type=action_type,
            target_type=target_type,
            target_id=target_id,
            details=details or {},
        )
        self.audit_repo.save(log)
        self.event_dispatcher.dispatch(AdminActionPerformed(
            admin_id=admin_id,
            action_type=action_type,
            target_type=target_type,
            target_id=target_id,
            occurred_at=utc_now(),
        ))

    @staticmethod
    def _to_flag_dto(f: ContentFlag) -> ContentFlagDTO:
        return ContentFlagDTO(
            id=f.id, reported_by=f.reported_by, content_type=f.content_type.value,
            content_id=f.content_id, reason=f.reason, status=f.status.value,
            admin_notes=f.admin_notes, created_at=f.created_at,
        )

    @staticmethod
    def _to_metric_dto(m: PlatformMetric) -> PlatformMetricDTO:
        return PlatformMetricDTO(
            date=m.date, total_users=m.total_users, total_planners=m.total_planners,
            total_vendors=m.total_vendors, active_vendors=m.active_vendors,
            pending_vendor_approvals=m.pending_vendor_approvals, total_events=m.total_events,
            total_inquiries=m.total_inquiries, total_reviews=m.total_reviews,
            updated_at=m.updated_at,
        )


class GovernanceQueryHandlers:
    def __init__(self, flag_repo: IContentFlagRepository, metric_repo: IPlatformMetricRepository,
                 audit_repo: IAuditLogRepository):
        self.flag_repo = flag_repo
        self.metric_repo = metric_repo
        self.audit_repo = audit_repo

    def list_pending_flags(self) -> List[ContentFlagDTO]:
        flags = self.flag_repo.list_pending()
        return [GovernanceCommandHandlers._to_flag_dto(f) for f in flags]

    def get_latest_metrics(self) -> Optional[PlatformMetricDTO]:
        metric = self.metric_repo.get_latest()
        return GovernanceCommandHandlers._to_metric_dto(metric) if metric else None