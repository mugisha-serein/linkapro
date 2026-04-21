import uuid
import json
from unittest.mock import patch, MagicMock
import pytest
from django.urls import reverse
from django.utils import timezone
from rest_framework.test import APIClient

from django_app.identity.models import User
from django_app.events.models import Event
from application.documents.dtos import ExportJobDTO

pytestmark = pytest.mark.django_db


class TestDocumentViews:
    @pytest.fixture(autouse=True)
    def setup(self):
        self.client = APIClient()
        self.user = User.objects.create_user(
            email="planner@test.com",
            password="pass123",
            first_name="Test",
            last_name="Planner",
            role="planner",
        )
        self.client.force_authenticate(user=self.user)
        self.event = Event.objects.create(
            planner=self.user,
            name="Wedding",
            event_type="wedding",
            event_date="2025-06-01"
        )

    def test_request_export_success(self):
        job_id = uuid.uuid4()
        dto = ExportJobDTO(
            id=job_id,
            event_id=self.event.id,
            export_type="event_brief",
            status="pending",
            file_url=None,
            error_message=None,
            created_at=timezone.now(),
        )

        # Patch at the location where the function is *used* inside the views module
        with patch("django_app.documents.views.get_command_handlers") as mock_get_cmd:
            mock_handlers = MagicMock()
            mock_handlers.request_export.return_value = dto
            mock_get_cmd.return_value = mock_handlers

            url = reverse("request-export", args=[str(self.event.id)])
            response = self.client.post(
                url,
                data=json.dumps({"export_type": "event_brief"}),
                content_type="application/json"
            )
            assert response.status_code == 202
            assert response.json()["status"] == "pending"

    def test_request_export_invalid_type(self):
        url = reverse("request-export", args=[str(self.event.id)])
        response = self.client.post(
            url,
            data=json.dumps({"export_type": "invalid"}),
            content_type="application/json"
        )
        assert response.status_code == 400

    def test_get_job_status(self):
        job_id = uuid.uuid4()
        dto = ExportJobDTO(
            id=job_id,
            event_id=self.event.id,
            export_type="budget",
            status="completed",
            file_url="https://cloud.com/file.xlsx",
            error_message=None,
            created_at=timezone.now(),
        )

        with patch("django_app.documents.views.get_query_handlers") as mock_get_qry:
            mock_handlers = MagicMock()
            mock_handlers.get_job.return_value = dto
            mock_get_qry.return_value = mock_handlers

            url = reverse("export-job-status", args=[str(job_id)])
            response = self.client.get(url)
            assert response.status_code == 200
            assert response.json()["status"] == "completed"