from rest_framework.views import APIView
from rest_framework.response import Response
from rest_framework import status
from rest_framework.permissions import IsAuthenticated

from .serializers import (
    CreateEventSerializer, UpdateEventSerializer, CreateChecklistSerializer,
    AddChecklistItemSerializer
)
from .services import get_command_handlers, get_query_handlers
from application.events.commands import DeleteEventCommand


class EventListCreateView(APIView):
    permission_classes = [IsAuthenticated]

    def get(self, request):
        handlers = get_query_handlers()
        events = handlers.list_events_by_planner(request.user.id)
        return Response([self._serialize_event(e) for e in events])

    def post(self, request):
        serializer = CreateEventSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        cmd = serializer.to_command(planner_id=request.user.id)
        handlers = get_command_handlers()
        event_dto = handlers.create_event(cmd)
        return Response(self._serialize_event(event_dto), status=status.HTTP_201_CREATED)

    def _serialize_event(self, dto):
        return serialize_event_dto(dto)


class EventDetailView(APIView):
    permission_classes = [IsAuthenticated]

    def get(self, request, event_id):
        handlers = get_query_handlers()
        event = handlers.get_event(event_id)
        if not event or event.planner_id != request.user.id:
            return Response({"error": "Not found"}, status=404)
        return Response(serialize_event_dto(event))

    def patch(self, request, event_id):
        query_handlers = get_query_handlers()
        event = query_handlers.get_event(event_id)
        if not event or event.planner_id != request.user.id:
            return Response({"error": "Not found"}, status=404)

        serializer = UpdateEventSerializer(data=request.data, partial=True)
        serializer.is_valid(raise_exception=True)
        cmd = serializer.to_command(event_id=event_id)
        command_handlers = get_command_handlers()
        updated = command_handlers.update_event(cmd)
        return Response(serialize_event_dto(updated))

    def delete(self, request, event_id):
        query_handlers = get_query_handlers()
        event = query_handlers.get_event(event_id)
        if not event or event.planner_id != request.user.id:
            return Response({"error": "Not found"}, status=404)

        command_handlers = get_command_handlers()
        command_handlers.delete_event(DeleteEventCommand(event_id=event_id))
        return Response(status=status.HTTP_204_NO_CONTENT)


def serialize_event_dto(dto):
    return {
        "id": str(dto.id),
        "planner_id": str(dto.planner_id),
        "name": dto.name,
        "event_type": dto.event_type,
        "event_date": dto.event_date.isoformat(),
        "venue": dto.venue,
        "expected_guests": dto.expected_guests,
        "total_budget": str(dto.total_budget),
        "created_at": dto.created_at.isoformat(),
        "updated_at": dto.updated_at.isoformat(),
    }
