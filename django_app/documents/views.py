from rest_framework.views import APIView
from rest_framework.response import Response
from rest_framework import status
from rest_framework.permissions import IsAuthenticated
from django.shortcuts import get_object_or_404

from .serializers import ExportRequestSerializer, ExportJobSerializer
from .services import get_command_handlers, get_query_handlers
from application.documents.commands import RequestExportCommand
from django_app.events.models import Event
import uuid


class ExportRequestView(APIView):
    permission_classes = [IsAuthenticated]

    def post(self, request, event_id):
        # Ensure the event belongs to the user
        event = get_object_or_404(Event, id=event_id, planner=request.user)

        serializer = ExportRequestSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)

        cmd = RequestExportCommand(
            event_id=event.id,
            requested_by=request.user.id,
            export_type=serializer.validated_data["export_type"],
        )

        handlers = get_command_handlers()
        job_dto = handlers.request_export(cmd)

        # Convert DTO to dict for response (serializer expects a model instance, but we have a DTO)
        # We can use the DTO directly or fetch the model. For simplicity, we'll return the DTO data.
        response_data = {
            "id": str(job_dto.id),
            "event_id": str(job_dto.event_id),
            "export_type": job_dto.export_type,
            "status": job_dto.status,
            "file_url": job_dto.file_url,
            "error_message": job_dto.error_message,
            "created_at": job_dto.created_at.isoformat(),
        }
        return Response(response_data, status=status.HTTP_202_ACCEPTED)


class ExportJobStatusView(APIView):
    permission_classes = [IsAuthenticated]

    def get(self, request, job_id):
        try:
            job_id = uuid.UUID(str(job_id))  # Ensure job_id is a string before conversion
        except ValueError:
            return Response({"error": "Invalid job ID format"}, status=status.HTTP_400_BAD_REQUEST)

        handlers = get_query_handlers()
        job_dto = handlers.get_job(job_id)

        if not job_dto:
            return Response({"error": "Export job not found"}, status=status.HTTP_404_NOT_FOUND)

        # Verify the job belongs to an event owned by the user
        event = Event.objects.filter(id=job_dto.event_id, planner=request.user).first()
        if not event:
            return Response({"error": "Not authorized to view this job"}, status=status.HTTP_403_FORBIDDEN)

        response_data = {
            "id": str(job_dto.id),
            "event_id": str(job_dto.event_id),
            "export_type": job_dto.export_type,
            "status": job_dto.status,
            "file_url": job_dto.file_url,
            "error_message": job_dto.error_message,
            "created_at": job_dto.created_at.isoformat(),
        }
        return Response(response_data, status=status.HTTP_200_OK)