from abc import ABC, abstractmethod
from typing import Optional, List
import uuid
from datetime import date

from .entities import AuditLog, ContentFlag, PlatformMetric, FlagStatus, ContentType


class IAuditLogRepository(ABC):
    @abstractmethod
    def save(self, log: AuditLog) -> AuditLog: ...
    @abstractmethod
    def list_by_admin(self, admin_id: uuid.UUID, limit: int = 100) -> List[AuditLog]: ...
    @abstractmethod
    def list_by_target(self, target_type: str, target_id: uuid.UUID) -> List[AuditLog]: ...


class IContentFlagRepository(ABC):
    @abstractmethod
    def get_by_id(self, flag_id: uuid.UUID) -> Optional[ContentFlag]: ...
    @abstractmethod
    def list_pending(self) -> List[ContentFlag]: ...
    @abstractmethod
    def list_by_content(self, content_type: ContentType, content_id: uuid.UUID) -> List[ContentFlag]: ...
    @abstractmethod
    def save(self, flag: ContentFlag) -> ContentFlag: ...


class IPlatformMetricRepository(ABC):
    @abstractmethod
    def get_for_date(self, date: date) -> Optional[PlatformMetric]: ...
    @abstractmethod
    def get_latest(self) -> Optional[PlatformMetric]: ...
    @abstractmethod
    def save(self, metric: PlatformMetric) -> PlatformMetric: ...
    @abstractmethod
    def generate_current_metrics(self) -> PlatformMetric: ...