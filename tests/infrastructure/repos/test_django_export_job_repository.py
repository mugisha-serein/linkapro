import uuid
import pytest
from django.utils import timezone

from domain.documents.entities import ExportJob as DomainJob, ExportType, ExportStatus
from infrastructure.repos.django_export_job_repository import DjangoExportJobRepository
from django_app.identity.models import User
from django_app.events.models import Event

pytestmark = pytest.mark.django_db


class TestDjangoExportJobRepository:
    def test_save_and_retrieve(self):
        user = User.objects.create_user(email="planner@test.com", password="p", role="planner")
        event = Event.objects.create(
            planner=user, name="Wedding", event_type="wedding", event_date="2025-06-01"
        )
        repo = DjangoExportJobRepository()
        domain_job = DomainJob(
            id=uuid.uuid4(),
            event_id=event.id,
            requested_by=user.id,
            export_type=ExportType.EVENT_BRIEF,
        )
        saved = repo.save(domain_job)
        assert saved.id == domain_job.id

        retrieved = repo.get_by_id(domain_job.id)
        assert retrieved is not None
        assert retrieved.export_type == ExportType.EVENT_BRIEF

    def test_list_by_user(self):
        user = User.objects.create_user(email="planner@test.com", password="p", role="planner")
        event = Event.objects.create(planner=user, name="Event", event_type="wedding", event_date="2025-01-01")
        repo = DjangoExportJobRepository()
        repo.save(DomainJob(id=uuid.uuid4(), event_id=event.id, requested_by=user.id, export_type=ExportType.BUDGET))
        repo.save(DomainJob(id=uuid.uuid4(), event_id=event.id, requested_by=user.id, export_type=ExportType.TIMELINE))
        jobs = repo.list_by_user(user.id)
        assert len(jobs) == 2

    def test_list_by_event(self):
        user = User.objects.create_user(email="planner@test.com", password="p", role="planner")
        event1 = Event.objects.create(planner=user, name="Event1", event_type="wedding", event_date="2025-01-01")
        event2 = Event.objects.create(planner=user, name="Event2", event_type="corporate", event_date="2025-02-01")
        repo = DjangoExportJobRepository()
        repo.save(DomainJob(id=uuid.uuid4(), event_id=event1.id, requested_by=user.id, export_type=ExportType.BUDGET))
        repo.save(DomainJob(id=uuid.uuid4(), event_id=event2.id, requested_by=user.id, export_type=ExportType.GUEST_LIST))
        assert len(repo.list_by_event(event1.id)) == 1
        assert len(repo.list_by_event(event2.id)) == 1