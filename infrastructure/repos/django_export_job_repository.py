import uuid
from typing import Optional, List
from django.core.exceptions import ObjectDoesNotExist

from domain.documents.entities import ExportJob as DomainJob, ExportType, ExportStatus
from domain.documents.interfaces import IExportJobRepository
from django_app.documents.models import ExportJob as DjangoJob
from django_app.events.models import Event as DjangoEvent
from django_app.identity.models import User as DjangoUser


class DjangoExportJobRepository(IExportJobRepository):
    def get_by_id(self, job_id: uuid.UUID) -> Optional[DomainJob]:
        try:
            job = DjangoJob.objects.select_related("event", "requested_by").get(id=job_id)
            return self._to_domain(job)
        except ObjectDoesNotExist:
            return None

    def list_by_user(self, user_id: uuid.UUID) -> List[DomainJob]:
        jobs = DjangoJob.objects.filter(requested_by_id=user_id).order_by("-created_at")
        return [self._to_domain(j) for j in jobs]

    def list_by_event(self, event_id: uuid.UUID) -> List[DomainJob]:
        jobs = DjangoJob.objects.filter(event_id=event_id).order_by("-created_at")
        return [self._to_domain(j) for j in jobs]

    def save(self, domain_job: DomainJob) -> DomainJob:
        try:
            django_job = DjangoJob.objects.get(id=domain_job.id)
        except DjangoJob.DoesNotExist:
            django_job = DjangoJob(id=domain_job.id)

        django_job.event = DjangoEvent.objects.get(id=domain_job.event_id)
        django_job.requested_by = DjangoUser.objects.get(id=domain_job.requested_by)
        django_job.export_type = domain_job.export_type.value
        django_job.status = domain_job.status.value
        django_job.file_url = domain_job.file_url
        django_job.error_message = domain_job.error_message
        django_job.save()
        return self._to_domain(django_job)

    def _to_domain(self, model: DjangoJob) -> DomainJob:
        return DomainJob(
            id=model.id,
            event_id=model.event_id,
            requested_by=model.requested_by_id,
            export_type=ExportType(model.export_type),
            status=ExportStatus(model.status),
            file_url=model.file_url,
            error_message=model.error_message,
            created_at=model.created_at,
            updated_at=model.updated_at,
        )