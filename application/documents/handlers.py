import uuid
from typing import List, Optional

from domain.shared.utils import utc_now
from domain.documents.entities import ExportJob, ExportType, ExportStatus
from domain.documents.interfaces import IExportJobRepository
from domain.documents.events import ExportRequested
from .commands import RequestExportCommand
from .dtos import ExportJobDTO


class DocumentCommandHandlers:
    def __init__(self, job_repo: IExportJobRepository, event_dispatcher):
        self.job_repo = job_repo
        self.event_dispatcher = event_dispatcher

    def request_export(self, cmd: RequestExportCommand) -> ExportJobDTO:
        job = ExportJob(
            id=uuid.uuid4(),
            event_id=cmd.event_id,
            requested_by=cmd.requested_by,
            export_type=ExportType(cmd.export_type),
        )
        saved = self.job_repo.save(job)
        self.event_dispatcher.dispatch(
            ExportRequested(
                job_id=saved.id,
                event_id=saved.event_id,
                export_type=saved.export_type,
                requested_by=saved.requested_by,
                occurred_at=utc_now(),
            )
        )
        return self._to_dto(saved)

    @staticmethod
    def _to_dto(job: ExportJob) -> ExportJobDTO:
        return ExportJobDTO(
            id=job.id,
            event_id=job.event_id,
            export_type=job.export_type.value,
            status=job.status.value,
            file_url=job.file_url,
            error_message=job.error_message,
            created_at=job.created_at,
        )


class DocumentQueryHandlers:
    def __init__(self, job_repo: IExportJobRepository):
        self.job_repo = job_repo

    def get_job(self, job_id: uuid.UUID) -> Optional[ExportJobDTO]:
        job = self.job_repo.get_by_id(job_id)
        return DocumentCommandHandlers._to_dto(job) if job else None

    def list_jobs_by_user(self, user_id: uuid.UUID) -> List[ExportJobDTO]:
        jobs = self.job_repo.list_by_user(user_id)
        return [DocumentCommandHandlers._to_dto(j) for j in jobs]