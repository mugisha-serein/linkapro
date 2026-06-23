from decimal import Decimal

from django.core.exceptions import ImproperlyConfigured
from django.db.models import Count, Q, Sum
from rest_framework import status
from rest_framework.permissions import IsAuthenticated
from rest_framework.response import Response
from rest_framework.views import APIView

from django_app.common.api_responses import api_error
from django_app.common.permissions import IsPlanner
from django_app.vendors.models import ServicePackage, VendorProfile

from .models import (
    Event,
    EventActivityLog,
    EventBudgetItem,
    EventDocument,
    EventQuestionAnswer,
    EventStage,
    EventTask,
    EventTimelineItem,
    EventVendorRequirement,
)
from .workspace_serializers import (
    EventBudgetItemSerializer,
    EventDocumentSerializer,
    EventQuestionAnswerSerializer,
    EventStageSerializer,
    EventTaskSerializer,
    EventTimelineItemSerializer,
    EventVendorRequirementSerializer,
)
from .workspace_service import generate_event_workspace, log_workspace_activity


def planner_event(event_id, user):
    return Event.objects.filter(id=event_id, planner_id=user.id).first()


def stage_for_event(event, stage_id):
    return EventStage.objects.filter(id=stage_id, event_id=event.id, event__planner_id=event.planner_id).first()


def paginated_response(request, queryset, serializer_class):
    try:
        page = max(int(request.query_params.get("page", 1)), 1)
        page_size = min(max(int(request.query_params.get("page_size", 50)), 1), 100)
    except ValueError:
        page, page_size = 1, 50
    count = queryset.count()
    start = (page - 1) * page_size
    return Response({"count": count, "page": page, "page_size": page_size, "results": serializer_class(queryset[start : start + page_size], many=True).data})


class PlannerWorkspaceView(APIView):
    permission_classes = [IsAuthenticated, IsPlanner]

    def get_event(self, request, event_id):
        return planner_event(event_id, request.user)

    def not_found(self):
        return Response({"error": "Not found"}, status=status.HTTP_404_NOT_FOUND)


class EventWorkspaceView(PlannerWorkspaceView):
    def get(self, request, event_id):
        event = self.get_event(request, event_id)
        if not event:
            return self.not_found()
        if event.event_type == Event.EventType.WEDDING and event.country.lower() == "rwanda":
            try:
                generate_event_workspace(event)
            except ImproperlyConfigured as exc:
                return api_error(
                    code="rwanda_wedding_template_missing",
                    message="We could not prepare your wedding workspace. Please try again or contact support.",
                    status=status.HTTP_500_INTERNAL_SERVER_ERROR,
                    extra={"detail": str(exc)},
                    request=request,
                )

        stages = event.workspace_stages.annotate(
            tasks_count=Count("tasks"),
            completed_tasks_count=Count("tasks", filter=Q(tasks__status=EventTask.Status.COMPLETED)),
        ).order_by("order", "id")
        budget = event.workspace_budget_items.aggregate(
            estimated=Sum("estimated_cost"), actual=Sum("actual_cost")
        )
        task_counts = event.workspace_tasks.aggregate(
            total=Count("id"), completed=Count("id", filter=Q(status=EventTask.Status.COMPLETED))
        )
        total_tasks = task_counts["total"] or 0
        return Response(
            {
                "event": {
                    "id": str(event.id),
                    "name": event.name,
                    "event_type": event.event_type,
                    "event_date": event.event_date.isoformat(),
                    "venue": event.venue,
                    "country": event.country,
                    "expected_guests": event.expected_guests,
                    "total_budget": str(event.total_budget),
                },
                "progress_percent": round(((task_counts["completed"] or 0) / total_tasks) * 100, 1) if total_tasks else 0,
                "task_summary": {"total": total_tasks, "completed": task_counts["completed"] or 0},
                "budget_summary": {
                    "estimated": str(budget["estimated"] or Decimal("0")),
                    "actual": str(budget["actual"] or Decimal("0")),
                },
                "vendor_summary": {
                    "total": event.workspace_vendor_requirements.count(),
                    "booked": event.workspace_vendor_requirements.filter(status=EventVendorRequirement.Status.BOOKED).count(),
                },
                "stages": EventStageSerializer(stages, many=True).data,
                "upcoming_tasks": EventTaskSerializer(event.workspace_tasks.exclude(status=EventTask.Status.COMPLETED).select_related("stage")[:8], many=True).data,
                "recent_activity": [serialize_activity(item) for item in event.workspace_activity.select_related("actor")[:10]],
            }
        )


class EventStageDetailView(PlannerWorkspaceView):
    def patch(self, request, event_id, stage_id):
        event = self.get_event(request, event_id)
        stage = stage_for_event(event, stage_id) if event else None
        if not stage:
            return self.not_found()
        serializer = EventStageSerializer(stage, data=request.data, partial=True)
        serializer.is_valid(raise_exception=True)
        serializer.save()
        log_workspace_activity(event, request.user, "stage_updated", stage, {"status": stage.status})
        return Response(serializer.data)


class WorkspaceCollectionView(PlannerWorkspaceView):
    model = None
    serializer_class = None
    related_name = None

    def queryset(self, event):
        return self.model.objects.filter(event_id=event.id, event__planner_id=event.planner_id).select_related("stage")

    def get(self, request, event_id):
        event = self.get_event(request, event_id)
        if not event:
            return self.not_found()
        queryset = self.queryset(event)
        stage_id = request.query_params.get("stage_id")
        status_value = request.query_params.get("status")
        if stage_id:
            queryset = queryset.filter(stage_id=stage_id)
        if status_value and any(field.name == "status" for field in self.model._meta.fields):
            queryset = queryset.filter(status=status_value)
        return paginated_response(request, queryset, self.serializer_class)

    def post(self, request, event_id):
        event = self.get_event(request, event_id)
        if not event:
            return self.not_found()
        stage = stage_for_event(event, request.data.get("stage")) if request.data.get("stage") else None
        if request.data.get("stage") and not stage:
            return Response({"stage": ["Stage not found for this event."]}, status=400)
        serializer = self.serializer_class(data=request.data)
        serializer.is_valid(raise_exception=True)
        instance = serializer.save(event=event)
        log_workspace_activity(event, request.user, f"{self.model._meta.model_name}_created", instance)
        return Response(self.serializer_class(instance).data, status=status.HTTP_201_CREATED)


class WorkspaceDetailView(PlannerWorkspaceView):
    model = None
    serializer_class = None

    def get_object(self, event, object_id):
        return self.model.objects.filter(id=object_id, event_id=event.id, event__planner_id=event.planner_id).select_related("stage").first()

    def patch(self, request, event_id, object_id):
        event = self.get_event(request, event_id)
        instance = self.get_object(event, object_id) if event else None
        if not instance:
            return self.not_found()
        if "stage" in request.data and not stage_for_event(event, request.data["stage"]):
            return Response({"stage": ["Stage not found for this event."]}, status=400)
        if self.model is EventVendorRequirement and request.data.get("assigned_vendor"):
            if not VendorProfile.objects.filter(
                id=request.data["assigned_vendor"], status=VendorProfile.Status.APPROVED
            ).exists():
                return Response({"assigned_vendor": ["Choose an approved vendor."]}, status=400)
        serializer = self.serializer_class(instance, data=request.data, partial=True)
        serializer.is_valid(raise_exception=True)
        serializer.save()
        log_workspace_activity(event, request.user, f"{self.model._meta.model_name}_updated", instance)
        return Response(serializer.data)

    def delete(self, request, event_id, object_id):
        event = self.get_event(request, event_id)
        instance = self.get_object(event, object_id) if event else None
        if not instance:
            return self.not_found()
        model_name = self.model._meta.model_name
        entity_id = instance.id
        instance.delete()
        EventActivityLog.objects.create(event=event, actor=request.user, action=f"{model_name}_deleted", entity_type=model_name, entity_id=entity_id)
        return Response(status=status.HTTP_204_NO_CONTENT)


class EventTaskListView(WorkspaceCollectionView):
    model = EventTask
    serializer_class = EventTaskSerializer


class EventTaskDetailView(WorkspaceDetailView):
    model = EventTask
    serializer_class = EventTaskSerializer


class EventBudgetItemListView(WorkspaceCollectionView):
    model = EventBudgetItem
    serializer_class = EventBudgetItemSerializer


class EventBudgetItemDetailView(WorkspaceDetailView):
    model = EventBudgetItem
    serializer_class = EventBudgetItemSerializer


class EventVendorRequirementListView(WorkspaceCollectionView):
    model = EventVendorRequirement
    serializer_class = EventVendorRequirementSerializer

    def queryset(self, event):
        return super().queryset(event).select_related("assigned_vendor")


class EventVendorRequirementDetailView(WorkspaceDetailView):
    model = EventVendorRequirement
    serializer_class = EventVendorRequirementSerializer


class EventQuestionAnswerListView(PlannerWorkspaceView):
    def get(self, request, event_id):
        event = self.get_event(request, event_id)
        if not event:
            return self.not_found()
        queryset = EventQuestionAnswer.objects.filter(event_id=event.id, event__planner_id=request.user.id).select_related("stage")
        if request.query_params.get("stage_id"):
            queryset = queryset.filter(stage_id=request.query_params["stage_id"])
        return paginated_response(request, queryset, EventQuestionAnswerSerializer)


class EventQuestionAnswerDetailView(WorkspaceDetailView):
    model = EventQuestionAnswer
    serializer_class = EventQuestionAnswerSerializer


class EventTimelineItemListView(WorkspaceCollectionView):
    model = EventTimelineItem
    serializer_class = EventTimelineItemSerializer


class EventTimelineItemDetailView(WorkspaceDetailView):
    model = EventTimelineItem
    serializer_class = EventTimelineItemSerializer


class EventDocumentListView(WorkspaceCollectionView):
    model = EventDocument
    serializer_class = EventDocumentSerializer


class EventDocumentDetailView(WorkspaceDetailView):
    model = EventDocument
    serializer_class = EventDocumentSerializer


class EventActivityView(PlannerWorkspaceView):
    def get(self, request, event_id):
        event = self.get_event(request, event_id)
        if not event:
            return self.not_found()
        items = EventActivityLog.objects.filter(event_id=event.id, event__planner_id=request.user.id).select_related("actor")
        return Response({"count": items.count(), "results": [serialize_activity(item) for item in items[:100]]})


class EventVendorRecommendationView(PlannerWorkspaceView):
    def get(self, request, event_id):
        event = self.get_event(request, event_id)
        if not event:
            return self.not_found()
        requirement = None
        if request.query_params.get("requirement_id"):
            requirement = EventVendorRequirement.objects.filter(
                id=request.query_params["requirement_id"], event_id=event.id, event__planner_id=request.user.id
            ).first()
            if not requirement:
                return self.not_found()
        category = request.query_params.get("category") or (requirement.category if requirement else None)
        vendors = VendorProfile.objects.filter(status=VendorProfile.Status.APPROVED)
        if category:
            vendors = vendors.filter(category=category)
        if event.venue:
            location = event.venue.split(",")[0].strip()
            vendors = vendors.filter(service_area__icontains=location)
        if requirement and requirement.maximum_budget is not None:
            vendors = vendors.filter(
                packages__is_deleted=False,
                packages__is_active=True,
                packages__approval_status=ServicePackage.ApprovalStatus.APPROVED,
                packages__price__lte=requirement.maximum_budget,
            )
        vendors = vendors.distinct().order_by("business_name")[:30]
        return Response({"count": len(vendors), "results": [serialize_vendor(vendor) for vendor in vendors]})


def serialize_activity(item):
    return {
        "id": str(item.id),
        "action": item.action,
        "entity_type": item.entity_type,
        "entity_id": str(item.entity_id) if item.entity_id else None,
        "details": item.details,
        "actor_name": " ".join(filter(None, (item.actor.first_name, item.actor.last_name))).strip() if item.actor else None,
        "created_at": item.created_at.isoformat(),
    }


def serialize_vendor(vendor):
    package = vendor.packages.filter(
        is_deleted=False,
        is_active=True,
        approval_status=ServicePackage.ApprovalStatus.APPROVED,
    ).order_by("price").first()
    return {
        "id": str(vendor.id),
        "business_name": vendor.business_name,
        "category": vendor.category,
        "service_area": vendor.service_area,
        "starting_price": str(package.price) if package else None,
        "currency": package.currency if package else "RWF",
    }
