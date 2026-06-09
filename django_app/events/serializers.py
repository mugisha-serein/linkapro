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


class UpdateChecklistItemSerializer(serializers.Serializer):
    description = serializers.CharField(required=False)
    status = serializers.ChoiceField(
        choices=["pending", "in_progress", "completed", "blocked"],
        required=False,
    )
    due_date = serializers.DateField(required=False, allow_null=True)
    assigned_to = serializers.CharField(required=False, allow_blank=True, allow_null=True)


class AddBudgetLineSerializer(serializers.Serializer):
    category = serializers.ChoiceField(
        choices=["venue", "catering", "photography", "decor", "entertainment", "transportation", "attire", "other"]
    )
    description = serializers.CharField()
    estimated_cost = serializers.DecimalField(max_digits=12, decimal_places=2)
    actual_cost = serializers.DecimalField(max_digits=12, decimal_places=2, required=False, allow_null=True)
    notes = serializers.CharField(required=False, allow_blank=True, allow_null=True)

    def to_command(self, event_id):
        return AddBudgetLineCommand(
            event_id=event_id,
            category=self.validated_data["category"],
            description=self.validated_data["description"],
            estimated_cost=float(self.validated_data["estimated_cost"]),
            actual_cost=float(self.validated_data["actual_cost"]) if self.validated_data.get("actual_cost") is not None else None,
            notes=self.validated_data.get("notes"),
        )


class AddGuestSerializer(serializers.Serializer):
    full_name = serializers.CharField(max_length=200)
    email = serializers.EmailField(required=False, allow_blank=True, allow_null=True)
    phone = serializers.CharField(max_length=30, required=False, allow_blank=True, allow_null=True)
    dietary_restrictions = serializers.ListField(
        child=serializers.CharField(),
        required=False,
        allow_empty=True,
        default=list,
    )
    plus_one = serializers.BooleanField(required=False, default=False)
    notes = serializers.CharField(required=False, allow_blank=True, allow_null=True)

    def to_command(self, event_id):
        return AddGuestCommand(
            event_id=event_id,
            full_name=self.validated_data["full_name"],
            email=self.validated_data.get("email"),
            phone=self.validated_data.get("phone"),
            dietary_restrictions=self.validated_data.get("dietary_restrictions", []),
            plus_one=self.validated_data.get("plus_one", False),
            notes=self.validated_data.get("notes"),
        )


class UpdateGuestSerializer(serializers.Serializer):
    full_name = serializers.CharField(max_length=200, required=False)
    email = serializers.EmailField(required=False, allow_blank=True, allow_null=True)
    phone = serializers.CharField(max_length=30, required=False, allow_blank=True, allow_null=True)
    rsvp_status = serializers.ChoiceField(
        choices=["pending", "accepted", "declined", "maybe"],
        required=False,
    )
    dietary_restrictions = serializers.ListField(
        child=serializers.CharField(),
        required=False,
        allow_empty=True,
    )
    plus_one = serializers.BooleanField(required=False)
    table_assignment = serializers.CharField(max_length=50, required=False, allow_blank=True, allow_null=True)
    notes = serializers.CharField(required=False, allow_blank=True, allow_null=True)


class AddTimelineBlockSerializer(serializers.Serializer):
    title = serializers.CharField(max_length=200)
    start_time = serializers.DateTimeField()
    end_time = serializers.DateTimeField()
    description = serializers.CharField(required=False, allow_blank=True, allow_null=True)
    location = serializers.CharField(max_length=300, required=False, allow_blank=True, allow_null=True)

    def to_command(self, event_id):
        return AddTimelineBlockCommand(
            event_id=event_id,
            title=self.validated_data["title"],
            start_time=self.validated_data["start_time"],
            end_time=self.validated_data["end_time"],
            description=self.validated_data.get("description"),
            location=self.validated_data.get("location"),
        )

class UpdateTimelineBlockSerializer(serializers.Serializer):
    title = serializers.CharField(max_length=200, required=False)
    start_time = serializers.DateTimeField(required=False)
    end_time = serializers.DateTimeField(required=False)
    description = serializers.CharField(required=False, allow_blank=True, allow_null=True)
    location = serializers.CharField(max_length=300, required=False, allow_blank=True, allow_null=True)
    order = serializers.IntegerField(min_value=0, required=False)
