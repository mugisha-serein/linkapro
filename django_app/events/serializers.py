from rest_framework import serializers
from application.events.commands import (
    CreateEventCommand, UpdateEventCommand, CreateChecklistCommand,
    AddChecklistItemCommand, AddBudgetLineCommand, AddGuestCommand,
    AddTimelineBlockCommand
)

class CreateEventSerializer(serializers.Serializer):
    name = serializers.CharField(max_length=200)
    event_type = serializers.ChoiceField(choices=["wedding", "travel", "corporate", "other"])
    event_date = serializers.DateField()
    venue = serializers.CharField(max_length=300, required=False, allow_blank=True)
    expected_guests = serializers.IntegerField(min_value=0, default=0)
    total_budget = serializers.DecimalField(max_digits=12, decimal_places=2, default=0.00)

    def to_command(self, planner_id):
        return CreateEventCommand(
            planner_id=planner_id,
            name=self.validated_data["name"],
            event_type=self.validated_data["event_type"],
            event_date=self.validated_data["event_date"],
            venue=self.validated_data.get("venue"),
            expected_guests=self.validated_data.get("expected_guests", 0),
            total_budget=float(self.validated_data.get("total_budget", 0.0)),
        )


class UpdateEventSerializer(serializers.Serializer):
    name = serializers.CharField(max_length=200, required=False)
    venue = serializers.CharField(max_length=300, required=False, allow_blank=True)
    expected_guests = serializers.IntegerField(min_value=0, required=False)
    total_budget = serializers.DecimalField(max_digits=12, decimal_places=2, required=False)

    def to_command(self, event_id):
        return UpdateEventCommand(
            event_id=event_id,
            name=self.validated_data.get("name"),
            venue=self.validated_data.get("venue"),
            expected_guests=self.validated_data.get("expected_guests"),
            total_budget=float(self.validated_data["total_budget"]) if "total_budget" in self.validated_data else None,
        )


class CreateChecklistSerializer(serializers.Serializer):
    name = serializers.CharField(max_length=200)

    def to_command(self, event_id):
        return CreateChecklistCommand(event_id=event_id, name=self.validated_data["name"])


class AddChecklistItemSerializer(serializers.Serializer):
    description = serializers.CharField()
    due_date = serializers.DateField(required=False, allow_null=True)
    assigned_to = serializers.CharField(required=False, allow_blank=True)

    def to_command(self, checklist_id):
        return AddChecklistItemCommand(
            checklist_id=checklist_id,
            description=self.validated_data["description"],
            due_date=self.validated_data.get("due_date"),
            assigned_to=self.validated_data.get("assigned_to"),
        )

# Similar serializers for Budget, Guest, Timeline (omitted for brevity)