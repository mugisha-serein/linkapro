import uuid
from django.db import models
from django.utils import timezone
from django_app.identity.models import User


class Event(models.Model):
    class EventType(models.TextChoices):
        WEDDING = "wedding"
        TRAVEL = "travel"
        CORPORATE = "corporate"
        OTHER = "other"

    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    planner = models.ForeignKey(User, on_delete=models.CASCADE, related_name="events")
    name = models.CharField(max_length=200)
    event_type = models.CharField(max_length=20, choices=EventType.choices)
    event_date = models.DateField()
    venue = models.CharField(max_length=300, blank=True, null=True)
    expected_guests = models.PositiveIntegerField(default=0)
    total_budget = models.DecimalField(max_digits=12, decimal_places=2, default=0.00)
    created_at = models.DateTimeField(default=timezone.now)
    updated_at = models.DateTimeField(auto_now=True)

    def __str__(self):
        return f"{self.name} ({self.planner.email})"


class EventVendorAssignment(models.Model):
    class Status(models.TextChoices):
        SHORTLISTED = "shortlisted"
        CONTACTED = "contacted"
        BOOKED = "booked"
        REJECTED = "rejected"

    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    event = models.ForeignKey(Event, on_delete=models.CASCADE, related_name="vendor_assignments")
    vendor = models.ForeignKey("vendors.VendorProfile", on_delete=models.CASCADE, related_name="event_assignments")
    status = models.CharField(max_length=20, choices=Status.choices, default=Status.SHORTLISTED)
    notes = models.TextField(blank=True, null=True)
    created_at = models.DateTimeField(default=timezone.now)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        constraints = [
            models.UniqueConstraint(fields=["event", "vendor"], name="unique_event_vendor_assignment"),
        ]
        indexes = [
            models.Index(fields=["event", "status"]),
            models.Index(fields=["vendor"]),
        ]

    def __str__(self):
        return f"{self.vendor.business_name} for {self.event.name}"


class Checklist(models.Model):
    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    event = models.ForeignKey(Event, on_delete=models.CASCADE, related_name="checklists")
    name = models.CharField(max_length=200)
    created_at = models.DateTimeField(default=timezone.now)
    updated_at = models.DateTimeField(auto_now=True)

    def __str__(self):
        return f"{self.name} - {self.event.name}"


class ChecklistItem(models.Model):
    class Status(models.TextChoices):
        PENDING = "pending"
        IN_PROGRESS = "in_progress"
        COMPLETED = "completed"
        BLOCKED = "blocked"

    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    checklist = models.ForeignKey(Checklist, on_delete=models.CASCADE, related_name="items")
    description = models.TextField()
    status = models.CharField(max_length=20, choices=Status.choices, default=Status.PENDING)
    due_date = models.DateField(blank=True, null=True)
    assigned_to = models.CharField(max_length=200, blank=True, null=True)
    order = models.PositiveIntegerField(default=0)
    created_at = models.DateTimeField(default=timezone.now)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        ordering = ["order"]

    def __str__(self):
        return self.description[:50]


class BudgetLine(models.Model):
    class Category(models.TextChoices):
        VENUE = "venue"
        CATERING = "catering"
        PHOTOGRAPHY = "photography"
        DECOR = "decor"
        ENTERTAINMENT = "entertainment"
        TRANSPORTATION = "transportation"
        ATTIRE = "attire"
        OTHER = "other"

    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    event = models.ForeignKey(Event, on_delete=models.CASCADE, related_name="budget_lines")
    category = models.CharField(max_length=20, choices=Category.choices)
    description = models.CharField(max_length=300)
    estimated_cost = models.DecimalField(max_digits=12, decimal_places=2)
    actual_cost = models.DecimalField(max_digits=12, decimal_places=2, blank=True, null=True)
    notes = models.TextField(blank=True, null=True)
    created_at = models.DateTimeField(default=timezone.now)
    updated_at = models.DateTimeField(auto_now=True)

    def __str__(self):
        return f"{self.category}: {self.description}"


class GuestEntry(models.Model):
    class RSVPStatus(models.TextChoices):
        PENDING = "pending"
        ACCEPTED = "accepted"
        DECLINED = "declined"
        MAYBE = "maybe"

    class DietaryRestriction(models.TextChoices):
        NONE = "none"
        VEGETARIAN = "vegetarian"
        VEGAN = "vegan"
        GLUTEN_FREE = "gluten_free"
        HALAL = "halal"
        KOSHER = "kosher"
        OTHER = "other"

    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    event = models.ForeignKey(Event, on_delete=models.CASCADE, related_name="guests")
    full_name = models.CharField(max_length=200)
    email = models.EmailField(blank=True, null=True)
    phone = models.CharField(max_length=30, blank=True, null=True)
    rsvp_status = models.CharField(max_length=20, choices=RSVPStatus.choices, default=RSVPStatus.PENDING)
    dietary_restrictions = models.JSONField(default=list)  # store list of strings
    plus_one = models.BooleanField(default=False)
    table_assignment = models.CharField(max_length=50, blank=True, null=True)
    notes = models.TextField(blank=True, null=True)
    created_at = models.DateTimeField(default=timezone.now)
    updated_at = models.DateTimeField(auto_now=True)

    def __str__(self):
        return self.full_name


class TimelineBlock(models.Model):
    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    event = models.ForeignKey(Event, on_delete=models.CASCADE, related_name="timeline_blocks")
    title = models.CharField(max_length=200)
    start_time = models.DateTimeField()
    end_time = models.DateTimeField()
    description = models.TextField(blank=True, null=True)
    location = models.CharField(max_length=300, blank=True, null=True)
    order = models.PositiveIntegerField(default=0)
    created_at = models.DateTimeField(default=timezone.now)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        ordering = ["order"]

    def __str__(self):
        return f"{self.title} ({self.start_time.strftime('%H:%M')} - {self.end_time.strftime('%H:%M')})"
