import uuid
from typing import List
from domain.governance.entities import AuditLog as DomainLog, AdminActionType
from domain.governance.interfaces import IAuditLogRepository
from django_app.governance.models import AuditLog as DjangoLog
from django_app.identity.models import User


class DjangoAuditLogRepository(IAuditLogRepository):
    def save(self, log: DomainLog) -> DomainLog:
        obj = DjangoLog.objects.create(
            id=log.id,
            admin_id=log.admin_id,
            action_type=log.action_type.value,
            target_type=log.target_type,
            target_id=log.target_id,
            details=log.details,
            created_at=log.created_at,
        )
        return self._to_domain(obj)

    def list_by_admin(self, admin_id: uuid.UUID, limit: int = 100) -> List[DomainLog]:
        objs = DjangoLog.objects.filter(admin_id=admin_id).order_by("-created_at")[:limit]
        return [self._to_domain(o) for o in objs]

    def list_by_target(self, target_type: str, target_id: uuid.UUID) -> List[DomainLog]:
        objs = DjangoLog.objects.filter(target_type=target_type, target_id=target_id)
        return [self._to_domain(o) for o in objs]

    def _to_domain(self, obj: DjangoLog) -> DomainLog:
        return DomainLog(
            id=obj.id,
            admin_id=obj.admin_id,
            action_type=AdminActionType(obj.action_type),
            target_type=obj.target_type,
            target_id=obj.target_id,
            details=obj.details,
            created_at=obj.created_at,
        )