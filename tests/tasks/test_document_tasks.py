import uuid
from unittest.mock import patch, Mock
import pytest

from tasks.document_tasks import generate_pdf_task, generate_excel_task
from domain.documents.entities import ExportJob, ExportType, ExportStatus


@pytest.mark.django_db
class TestDocumentTasks:
    @patch("evplan.tasks.document_tasks.DjangoExportJobRepository")
    @patch("evplan.tasks.document_tasks.CloudinaryAdapter")
    @patch("evplan.tasks.document_tasks.render_to_string")
    @patch("evplan.tasks.document_tasks.HTML")
    def test_generate_pdf_success(self, mock_html, mock_render, mock_cloud, mock_repo, event_factory):
        user = event_factory.planner
        event = event_factory()
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

        # Check job state
        assert job.status == ExportStatus.COMPLETED
        assert job.file_url == "https://cloud.com/file.pdf"
        mock_repo.return_value.save.assert_called()

    @patch("evplan.tasks.document_tasks.DjangoExportJobRepository")
    @patch("evplan.tasks.document_tasks.CloudinaryAdapter")
    @patch("evplan.tasks.document_tasks.openpyxl.Workbook")
    def test_generate_excel_success(self, mock_wb, mock_cloud, mock_repo, event_factory):
        user = event_factory.planner
        event = event_factory()
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