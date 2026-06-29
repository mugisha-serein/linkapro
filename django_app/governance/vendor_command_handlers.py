import logging

from django.db import transaction

from application.governance.handlers import GovernanceCommandHandlers
from domain.governance.entities import AdminActionType
from django_app.vendors.approval_workflow import approve_pending_vendor_submission
from django_app.vendors.models import VendorProfile
from infrastructure.adapters.marketplace_projection import sync_or_delete_vendor_projection

logger = logging.getLogger(__name__)


class DjangoGovernanceCommandHandlers(GovernanceCommandHandlers):
    def approve_vendor(self, cmd) -> None:
        approval = approve_pending_vendor_submission(cmd.vendor_id)
        self._log_action(
            cmd.admin_id,
            AdminActionType.APPROVE_VENDOR,
            "vendor",
            cmd.vendor_id,
            approval.summary(),
        )
        transaction.on_commit(lambda vendor_id=approval.vendor.id: self._sync_vendor_projection(vendor_id))

    @staticmethod
    def _sync_vendor_projection(vendor_id) -> None:
        try:
            vendor = VendorProfile.objects.get(id=vendor_id)
        except VendorProfile.DoesNotExist:
            return
        try:
            sync_or_delete_vendor_projection(vendor)
        except Exception:
            logger.exception("Vendor marketplace projection sync failed.", extra={"vendor_id": str(vendor_id)})
