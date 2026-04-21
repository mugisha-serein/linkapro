from rest_framework.views import APIView
from rest_framework.response import Response
from rest_framework import status
from rest_framework.permissions import IsAuthenticated

from .services import get_command_handlers, get_query_handlers
from application.documents.commands import RequestExportCommand
from application.documents.dtos import ExportJobDTO
import uuid


class ExportRequestView(APIView):
    permission_classes = [IsAuthenticated]

    def post(self, request, event_id):
        export_type = request.data.get("export_type")
        if export_type not in ["event_brief", "timeline", "budget", "guest_list"]:
            return Response({"error": "Invalid export type"}, status=400)

        cmd = RequestExportCommand(
            event_id=uuid.UUID(event_id),
            requested_by=request.user.id,
            export_type=export_type,
        )
        handlers = get_command_handlers()
        job_dto = handlers.request_export(cmd)
        return Response(self._serialize_job(job_dto), status=202)

    def _serialize_job(self, dto: ExportJobDTO):
        return {
            "id": str(dto.id),
            "event_id": str(dto.event_id),
            "export_type": dto.export_type,
            "status": dto.status,
            "file_url": dto.file_url,
            "error_message": dto.error_message,
            "created_at": dto.created_at.isoformat(),
        }


class ExportJobStatusView(APIView):
    permission_classes = [IsAuthenticated]

    def get(self, request, job_id):
        handlers = get_query_handlers()
        job = handlers.get_job(uuid.UUID(job_id))
        if not job or job.event_id not in request.user.events.values_list("id", flat=True):
            return Response({"error": "Not found"}, status=404)
        return Response(ExportRequestView._serialize_job(None, job))