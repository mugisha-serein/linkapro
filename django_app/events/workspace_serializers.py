from rest_framework import serializers

from .models import (
    EventBudgetItem,
    EventDocument,
    EventQuestionAnswer,
    EventStage,
    EventTask,
    EventTimelineItem,
    EventVendorRequirement,
)


class EventStageSerializer(serializers.ModelSerializer):
    tasks_count = serializers.IntegerField(read_only=True, required=False)
    completed_tasks_count = serializers.IntegerField(read_only=True, required=False)

    class Meta:
        model = EventStage
        fields = ("id", "event_id", "name", "slug", "description", "status", "order", "tasks_count", "completed_tasks_count", "updated_at")
        read_only_fields = ("id", "event_id", "slug", "order", "updated_at")


class EventTaskSerializer(serializers.ModelSerializer):
    stage_name = serializers.CharField(source="stage.name", read_only=True)

    class Meta:
        model = EventTask
        fields = ("id", "event_id", "stage", "stage_name", "title", "description", "status", "due_date", "assigned_to", "notes", "order", "created_at", "updated_at")
        read_only_fields = ("id", "event_id", "created_at", "updated_at")


class EventBudgetItemSerializer(serializers.ModelSerializer):
    stage_name = serializers.CharField(source="stage.name", read_only=True)

    class Meta:
        model = EventBudgetItem
        fields = ("id", "event_id", "stage", "stage_name", "category", "item", "estimated_cost", "actual_cost", "status", "notes", "order", "created_at", "updated_at")
        read_only_fields = ("id", "event_id", "created_at", "updated_at")


class EventVendorRequirementSerializer(serializers.ModelSerializer):
    stage_name = serializers.CharField(source="stage.name", read_only=True)
    assigned_vendor_name = serializers.CharField(source="assigned_vendor.business_name", read_only=True)

    class Meta:
        model = EventVendorRequirement
        fields = ("id", "event_id", "stage", "stage_name", "assigned_vendor", "assigned_vendor_name", "category", "title", "description", "minimum_budget", "maximum_budget", "status", "notes", "order", "created_at", "updated_at")
        read_only_fields = ("id", "event_id", "category", "created_at", "updated_at")


class EventQuestionAnswerSerializer(serializers.ModelSerializer):
    class Meta:
        model = EventQuestionAnswer
        fields = ("id", "event_id", "stage", "question", "answer", "created_at", "updated_at")
        read_only_fields = ("id", "event_id", "stage", "question", "created_at", "updated_at")


class EventTimelineItemSerializer(serializers.ModelSerializer):
    stage_name = serializers.CharField(source="stage.name", read_only=True)

    class Meta:
        model = EventTimelineItem
        fields = ("id", "event_id", "stage", "stage_name", "title", "scheduled_at", "location", "description", "status", "order", "created_at", "updated_at")
        read_only_fields = ("id", "event_id", "created_at", "updated_at")


class EventDocumentSerializer(serializers.ModelSerializer):
    stage_name = serializers.CharField(source="stage.name", read_only=True)

    class Meta:
        model = EventDocument
        fields = ("id", "event_id", "stage", "stage_name", "title", "document_type", "file_url", "notes", "created_at", "updated_at")
        read_only_fields = ("id", "event_id", "created_at", "updated_at")
