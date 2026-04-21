import uuid
import pytest
from datetime import datetime
from freezegun import freeze_time

from domain.documents.entities import ExportJob, ExportType, ExportStatus
from domain.shared.utils import utc_now


class TestExportJob:
    def test_create_job_defaults(self):
        job = ExportJob(
            id=uuid.uuid4(),
            event_id=uuid.uuid4(),
            requested_by=uuid.uuid4(),
            export_type=ExportType.EVENT_BRIEF,
        )
        assert job.status == ExportStatus.PENDING
        assert job.file_url is None
        assert job.error_message is None

    def test_mark_processing(self):
        job = ExportJob(
            id=uuid.uuid4(),
            event_id=uuid.uuid4(),
            requested_by=uuid.uuid4(),
            export_type=ExportType.TIMELINE,
        )
        frozen = datetime(2025, 1, 1, 12, 0, 0, tzinfo=utc_now().tzinfo)
        with freeze_time(frozen):
            job.mark_processing()
        assert job.status == ExportStatus.PROCESSING
        assert job.updated_at == frozen

    def test_complete(self):
        job = ExportJob(
            id=uuid.uuid4(),
            event_id=uuid.uuid4(),
            requested_by=uuid.uuid4(),
            export_type=ExportType.BUDGET,
        )
        frozen = datetime(2025, 1, 1, 12, 0, 0, tzinfo=utc_now().tzinfo)
        with freeze_time(frozen):
            job.complete("https://cloudinary.com/file.xlsx")
        assert job.status == ExportStatus.COMPLETED
        assert job.file_url == "https://cloudinary.com/file.xlsx"
        assert job.updated_at == frozen

    def test_fail(self):
        job = ExportJob(
            id=uuid.uuid4(),
            event_id=uuid.uuid4(),
            requested_by=uuid.uuid4(),
            export_type=ExportType.GUEST_LIST,
        )
        frozen = datetime(2025, 1, 1, 12, 0, 0, tzinfo=utc_now().tzinfo)
        with freeze_time(frozen):
            job.fail("Database connection error")
        assert job.status == ExportStatus.FAILED
        assert job.error_message == "Database connection error"
        assert job.updated_at == frozen