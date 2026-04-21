import uuid
from unittest.mock import patch, MagicMock
import pytest

from tasks.document_tasks import generate_pdf_task, generate_excel_task
from domain.documents.entities import ExportJob, ExportType, ExportStatus


@pytest.mark.django_db
class TestDocumentTasks:
    @patch("tasks.document_tasks.HTML")
    @patch("tasks.document_tasks.render_to_string")
    @patch("tasks.document_tasks.CloudinaryAdapter")
    @patch("tasks.document_tasks.DjangoExportJobRepository")
    def test_generate_pdf_success(self, mock_repo, mock_cloud, mock_render, mock_html, event_factory):
        event = event_factory()
        user = event.planner
        job = ExportJob(
            id=uuid.uuid4(),
            event_id=event.id,
            requested_by=user.id,
            export_type=ExportType.EVENT_BRIEF,
        )
        mock_repo.return_value.get_by_id.return_value = job
        mock_repo.return_value.save.side_effect = lambda j: j
        mock_render.return_value = "<html></html>"
        mock_cloud.return_value.upload_file.return_value = {"secure_url": "https://cloud.com/file.pdf"}

        generate_pdf_task(str(job.id), str(event.id), "event_brief")

        assert job.status == ExportStatus.COMPLETED
        assert job.file_url == "https://cloud.com/file.pdf"
        mock_repo.return_value.save.assert_called()

    @patch("tasks.document_tasks.CloudinaryAdapter")
    @patch("tasks.document_tasks.DjangoExportJobRepository")
    def test_generate_excel_success(self, mock_repo, mock_cloud, event_factory):
        event = event_factory()
        user = event.planner
        job = ExportJob(
            id=uuid.uuid4(),
            event_id=event.id,
            requested_by=user.id,
            export_type=ExportType.BUDGET,
        )
        mock_repo.return_value.get_by_id.return_value = job
        mock_repo.return_value.save.side_effect = lambda j: j
        mock_cloud.return_value.upload_file.return_value = {"secure_url": "https://cloud.com/file.xlsx"}

        generate_excel_task(str(job.id), str(event.id), "budget")

        assert job.status == ExportStatus.COMPLETED
        assert job.file_url == "https://cloud.com/file.xlsx"
        mock_repo.return_value.save.assert_called()