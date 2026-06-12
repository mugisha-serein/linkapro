from rest_framework.views import APIView
from rest_framework.response import Response
from rest_framework import status
from rest_framework.permissions import IsAuthenticated
from django_app.common.permissions import IsPlanner
from django_app.vendors.models import VendorProfile
from .models import Event, EventVendorAssignment, GuestEntry, TimelineBlock

from .serializers import (
    CreateEventSerializer, UpdateEventSerializer, CreateChecklistSerializer,
    AddChecklistItemSerializer, UpdateChecklistItemSerializer, AddBudgetLineSerializer,
    AddGuestSerializer, UpdateGuestSerializer, AddTimelineBlockSerializer, UpdateTimelineBlockSerializer,
    AddEventVendorAssignmentSerializer, UpdateEventVendorAssignmentSerializer,
)
from .services import get_command_handlers, get_query_handlers
from application.events.commands import (
    DeleteEventCommand, UpdateChecklistItemCommand, UpdateBudgetLineCommand,
    UpdateGuestCommand,
)
from application.events.dtos import ChecklistDTO, ChecklistItemDTO, GuestEntryDTO, DashboardSummaryDTO


class EventListCreateView(APIView):
    permission_classes = [IsAuthenticated, IsPlanner]

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
    permission_classes = [IsAuthenticated, IsPlanner]

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


class ChecklistListCreateView(APIView):
    permission_classes = [IsAuthenticated, IsPlanner]

    def get(self, request, event_id):
        query_handlers = get_query_handlers()
        event = query_handlers.get_event(event_id)
        if not event or event.planner_id != request.user.id:
            return Response({"error": "Not found"}, status=404)

        checklists = query_handlers.list_checklists_by_event(event_id)
        return Response([serialize_checklist_dto(checklist) for checklist in checklists])

    def post(self, request, event_id):
        query_handlers = get_query_handlers()
        event = query_handlers.get_event(event_id)
        if not event or event.planner_id != request.user.id:
            return Response({"error": "Not found"}, status=404)

        serializer = CreateChecklistSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        cmd = serializer.to_command(event_id=event_id)
        command_handlers = get_command_handlers()
        checklist = command_handlers.create_checklist(cmd)
        return Response(serialize_checklist_dto(checklist), status=status.HTTP_201_CREATED)


class ChecklistItemListCreateView(APIView):
    permission_classes = [IsAuthenticated, IsPlanner]

    def get(self, request, checklist_id):
        query_handlers = get_query_handlers()
        checklist = query_handlers.get_checklist(checklist_id)
        if not checklist:
            return Response({"error": "Not found"}, status=404)

        event = query_handlers.get_event(checklist.event_id)
        if not event or event.planner_id != request.user.id:
            return Response({"error": "Not found"}, status=404)

        items = query_handlers.list_checklist_items(checklist_id)
        return Response([serialize_checklist_item_dto(item) for item in items])

    def post(self, request, checklist_id):
        query_handlers = get_query_handlers()
        checklist = query_handlers.get_checklist(checklist_id)
        if not checklist:
            return Response({"error": "Not found"}, status=404)

        event = query_handlers.get_event(checklist.event_id)
        if not event or event.planner_id != request.user.id:
            return Response({"error": "Not found"}, status=404)

        serializer = AddChecklistItemSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        cmd = serializer.to_command(checklist_id=checklist_id)
        command_handlers = get_command_handlers()
        item = command_handlers.add_checklist_item(cmd)
        return Response(serialize_checklist_item_dto(item), status=status.HTTP_201_CREATED)


class ChecklistItemDetailView(APIView):
    permission_classes = [IsAuthenticated, IsPlanner]

    def patch(self, request, item_id):
        query_handlers = get_query_handlers()
        item = query_handlers.checklist_item_repo.get_by_id(item_id)
        if not item:
            return Response({"error": "Not found"}, status=404)

        checklist = query_handlers.get_checklist(item.checklist_id)
        event = query_handlers.get_event(checklist.event_id) if checklist else None
        if not checklist or not event or event.planner_id != request.user.id:
            return Response({"error": "Not found"}, status=404)

        serializer = UpdateChecklistItemSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        cmd = UpdateChecklistItemCommand(
            item_id=item.id,
            description=serializer.validated_data.get("description"),
            status=serializer.validated_data.get("status"),
            due_date=serializer.validated_data.get("due_date"),
            assigned_to=serializer.validated_data.get("assigned_to"),
        )

        command_handlers = get_command_handlers()
        saved = command_handlers.update_checklist_item(cmd)
        return Response(serialize_checklist_item_dto(saved))


class BudgetLineListCreateView(APIView):
    permission_classes = [IsAuthenticated, IsPlanner]

    def get(self, request, event_id):
        query_handlers = get_query_handlers()
        event = query_handlers.get_event(event_id)
        if not event or event.planner_id != request.user.id:
            return Response({"error": "Not found"}, status=404)

        lines = query_handlers.list_budget_lines(event_id)
        return Response([serialize_budget_line_dto(line) for line in lines])

    def post(self, request, event_id):
        query_handlers = get_query_handlers()
        event = query_handlers.get_event(event_id)
        if not event or event.planner_id != request.user.id:
            return Response({"error": "Not found"}, status=404)

        serializer = AddBudgetLineSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        cmd = serializer.to_command(event_id=event_id)
        command_handlers = get_command_handlers()
        line = command_handlers.add_budget_line(cmd)
        return Response(serialize_budget_line_dto(line), status=status.HTTP_201_CREATED)


class BudgetLineDetailView(APIView):
    permission_classes = [IsAuthenticated, IsPlanner]

    def patch(self, request, line_id):
        query_handlers = get_query_handlers()
        line = query_handlers.budget_repo.get_by_id(line_id)
        if not line:
            return Response({"error": "Not found"}, status=404)

        event = query_handlers.get_event(line.event_id)
        if not event or event.planner_id != request.user.id:
            return Response({"error": "Not found"}, status=404)

        serializer = AddBudgetLineSerializer(data=request.data, partial=True)
        serializer.is_valid(raise_exception=True)
        cmd = UpdateBudgetLineCommand(
            line_id=line.id,
            estimated_cost=float(serializer.validated_data["estimated_cost"]) if "estimated_cost" in serializer.validated_data else None,
            actual_cost=float(serializer.validated_data["actual_cost"]) if serializer.validated_data.get("actual_cost") is not None else None,
            notes=serializer.validated_data.get("notes"),
        )
        command_handlers = get_command_handlers()
        updated = command_handlers.update_budget_line(cmd)
        return Response(serialize_budget_line_dto(updated))


class GuestListCreateView(APIView):
    permission_classes = [IsAuthenticated, IsPlanner]

    def get(self, request, event_id):
        query_handlers = get_query_handlers()
        event = query_handlers.get_event(event_id)
        if not event or event.planner_id != request.user.id:
            return Response({"error": "Not found"}, status=404)

        guests = query_handlers.list_guests(event_id)
        return Response([serialize_guest_dto(guest) for guest in guests])

    def post(self, request, event_id):
        query_handlers = get_query_handlers()
        event = query_handlers.get_event(event_id)
        if not event or event.planner_id != request.user.id:
            return Response({"error": "Not found"}, status=404)

        serializer = AddGuestSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        cmd = serializer.to_command(event_id=event_id)
        command_handlers = get_command_handlers()
        guest = command_handlers.add_guest(cmd)
        return Response(serialize_guest_dto(guest), status=status.HTTP_201_CREATED)


class GuestDetailView(APIView):
    permission_classes = [IsAuthenticated, IsPlanner]

    def patch(self, request, guest_id):
        query_handlers = get_query_handlers()
        guest = GuestEntry.objects.filter(id=guest_id).first()
        if not guest:
            return Response({"error": "Not found"}, status=404)

        event = query_handlers.get_event(guest.event_id)
        if not event or event.planner_id != request.user.id:
            return Response({"error": "Not found"}, status=404)

        serializer = UpdateGuestSerializer(data=request.data, partial=True)
        serializer.is_valid(raise_exception=True)
        data = serializer.validated_data
        cmd = UpdateGuestCommand(
            guest_id=guest.id,
            full_name=data.get("full_name"),
            email=data.get("email"),
            phone=data.get("phone"),
            rsvp_status=data.get("rsvp_status"),
            dietary_restrictions=data.get("dietary_restrictions"),
            plus_one=data.get("plus_one"),
            table_assignment=data.get("table_assignment"),
            notes=data.get("notes"),
        )
        updated = get_command_handlers().update_guest(cmd)
        return Response(serialize_guest_dto(updated))


class TimelineBlockListCreateView(APIView):
    permission_classes = [IsAuthenticated, IsPlanner]

    def get(self, request, event_id):
        query_handlers = get_query_handlers()
        event = query_handlers.get_event(event_id)
        if not event or event.planner_id != request.user.id:
            return Response({"error": "Not found"}, status=404)

        blocks = query_handlers.list_timeline_blocks(event_id)
        return Response([serialize_timeline_block_dto(block) for block in blocks])

    def post(self, request, event_id):
        query_handlers = get_query_handlers()
        event = query_handlers.get_event(event_id)
        if not event or event.planner_id != request.user.id:
            return Response({"error": "Not found"}, status=404)

        serializer = AddTimelineBlockSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        cmd = serializer.to_command(event_id=event_id)
        command_handlers = get_command_handlers()
        block = command_handlers.add_timeline_block(cmd)
        return Response(serialize_timeline_block_dto(block), status=status.HTTP_201_CREATED)


class TimelineBlockDetailView(APIView):
    permission_classes = [IsAuthenticated, IsPlanner]

    def patch(self, request, block_id):
        query_handlers = get_query_handlers()
        block = TimelineBlock.objects.filter(id=block_id).first()
        if not block:
            return Response({"error": "Not found"}, status=404)

        event = query_handlers.get_event(block.event_id)
        if not event or event.planner_id != request.user.id:
            return Response({"error": "Not found"}, status=404)

        serializer = UpdateTimelineBlockSerializer(data=request.data, partial=True)
        serializer.is_valid(raise_exception=True)
        for field, value in serializer.validated_data.items():
            setattr(block, field, value)
        block.save()

        return Response(serialize_timeline_block_dto(block))


class EventVendorAssignmentListCreateView(APIView):
    permission_classes = [IsAuthenticated, IsPlanner]

    def get(self, request, event_id):
        event = get_planner_event(event_id, request.user)
        if not event:
            return Response({"error": "Not found"}, status=404)

        assignments = EventVendorAssignment.objects.filter(event=event).select_related("vendor").order_by("-created_at")
        return Response([serialize_event_vendor_assignment(assignment) for assignment in assignments])

    def post(self, request, event_id):
        event = get_planner_event(event_id, request.user)
        if not event:
            return Response({"error": "Not found"}, status=404)

        serializer = AddEventVendorAssignmentSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        vendor = VendorProfile.objects.filter(id=serializer.validated_data["vendor_id"]).first()
        if not vendor:
            return Response({"vendor_id": ["Vendor not found."]}, status=status.HTTP_400_BAD_REQUEST)

        assignment = EventVendorAssignment.objects.filter(event=event, vendor=vendor).select_related("vendor").first()
        if assignment:
            return Response(serialize_event_vendor_assignment(assignment))

        assignment = EventVendorAssignment.objects.create(
            event=event,
            vendor=vendor,
            notes=serializer.validated_data.get("notes"),
        )
        assignment.vendor = vendor
        return Response(serialize_event_vendor_assignment(assignment), status=status.HTTP_201_CREATED)


class EventVendorAssignmentDetailView(APIView):
    permission_classes = [IsAuthenticated, IsPlanner]

    def patch(self, request, event_id, assignment_id):
        assignment = get_planner_event_vendor_assignment(event_id, assignment_id, request.user)
        if not assignment:
            return Response({"error": "Not found"}, status=404)

        serializer = UpdateEventVendorAssignmentSerializer(data=request.data, partial=True)
        serializer.is_valid(raise_exception=True)
        for field in ("status", "notes"):
            if field in serializer.validated_data:
                setattr(assignment, field, serializer.validated_data[field])
        assignment.save()
        return Response(serialize_event_vendor_assignment(assignment))

    def delete(self, request, event_id, assignment_id):
        assignment = get_planner_event_vendor_assignment(event_id, assignment_id, request.user)
        if not assignment:
            return Response({"error": "Not found"}, status=404)

        assignment.delete()
        return Response(status=status.HTTP_204_NO_CONTENT)


def get_planner_event(event_id, user):
    return Event.objects.filter(id=event_id, planner=user).first()


def get_planner_event_vendor_assignment(event_id, assignment_id, user):
    return (
        EventVendorAssignment.objects.filter(id=assignment_id, event_id=event_id, event__planner=user)
        .select_related("vendor")
        .first()
    )


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
        "vendors_count": EventVendorAssignment.objects.filter(event_id=dto.id).count(),
        "progress_percent": getattr(dto, "progress_percent", 0.0),
    }


def serialize_checklist_dto(dto: ChecklistDTO):
    return {
        "id": str(dto.id),
        "event_id": str(dto.event_id),
        "name": dto.name,
        "created_at": getattr(dto, "created_at", None).isoformat() if getattr(dto, "created_at", None) else None,
        "updated_at": getattr(dto, "updated_at", None).isoformat() if getattr(dto, "updated_at", None) else None,
    }


def serialize_checklist_item_dto(dto: ChecklistItemDTO):
    return {
        "id": str(dto.id),
        "checklist_id": str(dto.checklist_id),
        "description": dto.description,
        "status": dto.status,
        "due_date": dto.due_date.isoformat() if dto.due_date else None,
        "assigned_to": dto.assigned_to,
        "order": dto.order,
        "created_at": dto.created_at.isoformat() if dto.created_at else None,
        "updated_at": dto.updated_at.isoformat() if dto.updated_at else None,
    }


def serialize_budget_line_dto(dto):
    return {
        "id": str(dto.id),
        "event_id": str(dto.event_id),
        "category": dto.category,
        "description": dto.description,
        "estimated_cost": str(dto.estimated_cost),
        "actual_cost": str(dto.actual_cost) if dto.actual_cost is not None else None,
        "notes": dto.notes,
        "created_at": getattr(dto, "created_at", None).isoformat() if getattr(dto, "created_at", None) else None,
        "updated_at": getattr(dto, "updated_at", None).isoformat() if getattr(dto, "updated_at", None) else None,
    }


def serialize_guest_dto(dto: GuestEntryDTO):
    return {
        "id": str(dto.id),
        "event_id": str(dto.event_id),
        "full_name": dto.full_name,
        "email": dto.email,
        "phone": dto.phone,
        "rsvp_status": dto.rsvp_status,
        "dietary_restrictions": dto.dietary_restrictions,
        "plus_one": dto.plus_one,
        "table_assignment": dto.table_assignment,
        "notes": dto.notes,
        "created_at": getattr(dto, "created_at", None).isoformat() if getattr(dto, "created_at", None) else None,
        "updated_at": getattr(dto, "updated_at", None).isoformat() if getattr(dto, "updated_at", None) else None,
    }


def serialize_timeline_block_dto(dto):
    return {
        "id": str(dto.id),
        "event_id": str(dto.event_id),
        "title": dto.title,
        "start_time": dto.start_time.isoformat(),
        "end_time": dto.end_time.isoformat(),
        "description": dto.description,
        "location": dto.location,
        "order": dto.order,
        "created_at": getattr(dto, "created_at", None).isoformat() if getattr(dto, "created_at", None) else None,
        "updated_at": getattr(dto, "updated_at", None).isoformat() if getattr(dto, "updated_at", None) else None,
    }


def serialize_event_vendor_assignment(assignment: EventVendorAssignment):
    return {
        "id": str(assignment.id),
        "event_id": str(assignment.event_id),
        "vendor_id": str(assignment.vendor_id),
        "business_name": assignment.vendor.business_name,
        "vendor_name": assignment.vendor.business_name,
        "category": assignment.vendor.category,
        "service_area": assignment.vendor.service_area,
        "status": assignment.status,
        "notes": assignment.notes,
        "created_at": assignment.created_at.isoformat() if assignment.created_at else None,
        "updated_at": assignment.updated_at.isoformat() if assignment.updated_at else None,
    }


class DashboardSummaryView(APIView):
    permission_classes = [IsAuthenticated, IsPlanner]

    def get(self, request):
        handlers = get_query_handlers()
        summary = handlers.get_dashboard_summary(request.user.id)
        data = serialize_dashboard_summary_dto(summary)
        data["vendors_linked_count"] = (
            EventVendorAssignment.objects.filter(event__planner=request.user).values("vendor_id").distinct().count()
        )
        return Response(data)

def serialize_dashboard_summary_dto(dto: DashboardSummaryDTO):
    return {
        "active_events_count": dto.active_events_count,
        "open_tasks_count": dto.open_tasks_count,
        "budget_usage_percent": dto.budget_usage_percent,
        "vendors_linked_count": dto.vendors_linked_count,
        "upcoming_events": [serialize_event_dto(e) for e in dto.upcoming_events],
        "recent_tasks": [serialize_checklist_item_dto(t) for t in dto.recent_tasks],
    }
