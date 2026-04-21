from abc import ABC, abstractmethod
from typing import Optional, List
import uuid

from .entities import ExportJob


class IExportJobRepository(ABC):
    @abstractmethod
    def get_by_id(self, job_id: uuid.UUID) -> Optional[ExportJob]: ...
    @abstractmethod
    def list_by_user(self, user_id: uuid.UUID) -> List[ExportJob]: ...
    @abstractmethod
    def list_by_event(self, event_id: uuid.UUID) -> List[ExportJob]: ...
    @abstractmethod
    def save(self, job: ExportJob) -> ExportJob: ...