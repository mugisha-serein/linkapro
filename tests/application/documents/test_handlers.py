import uuid
import pytest
from unittest.mock import Mock

from application.documents.commands import RequestExportCommand
from application.documents.handlers import DocumentCommandHandlers, DocumentQueryHandlers
from domain.documents.entities import ExportJob, ExportType, ExportStatus


@pytest.fixture
def mock_job_repo():
    return Mock()


@pytest.fixture
def mock_event_dispatcher():
    return Mock()


@pytest.fixture
def command_handlers(mock_job_repo, mock_event_dispatcher):
    return DocumentCommandHandlers(
        job_repo=mock_job_repo,
        event_dispatcher=mock_event_dispatcher,
    )


@pytest.fixture
def query_handlers(mock_job_repo):
    return DocumentQueryHandlers(job_repo=mock_job_repo)


class TestDocumentCommandHandlers:
    def test_request_export_success(self, command_handlers, mock_job_repo, mock_event_dispatcher):
        mock_job_repo.save.side_effect = lambda j: j

        cmd = RequestExportCommand(
            event_id=uuid.uuid4(),
            requested_by=uuid.uuid4(),
            export_type="event_brief",
        )
        result = command_handlers.request_export(cmd)

        assert result.export_type == "event_brief"
        assert result.status == "pending"
        mock_job_repo.save.assert_called_once()
        mock_event_dispatcher.dispatch.assert_called_once()


class TestDocumentQueryHandlers:
    def test_get_job_found(self, query_handlers, mock_job_repo):
        job_id = uuid.uuid4()
        job = ExportJob(
            id=job_id,
            event_id=uuid.uuid4(),
            requested_by=uuid.uuid4(),
            export_type=ExportType.TIMELINE,
        )
        mock_job_repo.get_by_id.return_value = job

        result = query_handlers.get_job(job_id)
        assert result is not None
        assert result.id == job_id

    def test_get_job_not_found(self, query_handlers, mock_job_repo):
        mock_job_repo.get_by_id.return_value = None
        result = query_handlers.get_job(uuid.uuid4())
        assert result is None

    def test_list_jobs_by_user(self, query_handlers, mock_job_repo):
        user_id = uuid.uuid4()
        jobs = [
            ExportJob(id=uuid.uuid4(), event_id=uuid.uuid4(), requested_by=user_id, export_type=ExportType.BUDGET),
            ExportJob(id=uuid.uuid4(), event_id=uuid.uuid4(), requested_by=user_id, export_type=ExportType.GUEST_LIST),
        ]
        mock_job_repo.list_by_user.return_value = jobs

        results = query_handlers.list_jobs_by_user(user_id)
        assert len(results) == 2