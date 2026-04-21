from infrastructure.repos.django_audit_log_repository import DjangoAuditLogRepository
from infrastructure.repos.django_content_flag_repository import DjangoContentFlagRepository
from infrastructure.repos.django_platform_metric_repository import DjangoPlatformMetricRepository
from infrastructure.repos.django_vendor_profile_repository import DjangoVendorProfileRepository
from infrastructure.repos.django_user_repository import DjangoUserRepository
from infrastructure.adapters.django_event_dispatcher import DjangoEventDispatcher
from application.governance.handlers import GovernanceCommandHandlers, GovernanceQueryHandlers

def get_command_handlers():
    return GovernanceCommandHandlers(
        audit_repo=DjangoAuditLogRepository(),
        flag_repo=DjangoContentFlagRepository(),
        metric_repo=DjangoPlatformMetricRepository(),
        vendor_repo=DjangoVendorProfileRepository(),
        user_repo=DjangoUserRepository(),
        event_dispatcher=DjangoEventDispatcher(),
    )

def get_query_handlers():
    return GovernanceQueryHandlers(
        flag_repo=DjangoContentFlagRepository(),
        metric_repo=DjangoPlatformMetricRepository(),
        audit_repo=DjangoAuditLogRepository(),
    )