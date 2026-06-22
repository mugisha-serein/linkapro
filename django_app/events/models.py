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
    country = models.CharField(max_length=100, default="Rwanda")
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


class EventTemplate(models.Model):
    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    slug = models.SlugField(max_length=120, unique=True)
    name = models.CharField(max_length=200)
    event_type = models.CharField(max_length=20, choices=Event.EventType.choices)
    country = models.CharField(max_length=100)
    description = models.TextField(blank=True)
    version = models.PositiveIntegerField(default=1)
    is_active = models.BooleanField(default=True)
    created_at = models.DateTimeField(default=timezone.now)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        indexes = [models.Index(fields=["event_type", "country", "is_active"])]


class EventStageTemplate(models.Model):
    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    template = models.ForeignKey(EventTemplate, on_delete=models.CASCADE, related_name="stages")
    name = models.CharField(max_length=200)
    slug = models.SlugField(max_length=120)
    description = models.TextField(blank=True)
    order = models.PositiveIntegerField(default=0)

    class Meta:
        ordering = ["order", "id"]
        constraints = [models.UniqueConstraint(fields=["template", "slug"], name="unique_template_stage_slug")]
        indexes = [models.Index(fields=["template", "order"])]


class EventTaskTemplate(models.Model):
    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    stage = models.ForeignKey(EventStageTemplate, on_delete=models.CASCADE, related_name="tasks")
    title = models.CharField(max_length=300)
    description = models.TextField(blank=True)
    days_before_event = models.IntegerField(blank=True, null=True)
    order = models.PositiveIntegerField(default=0)

    class Meta:
        ordering = ["order", "id"]
        indexes = [models.Index(fields=["stage", "order"])]


class EventBudgetItemTemplate(models.Model):
    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    stage = models.ForeignKey(EventStageTemplate, on_delete=models.CASCADE, related_name="budget_items")
    category = models.CharField(max_length=120)
    item = models.CharField(max_length=300)
    estimated_cost = models.DecimalField(max_digits=14, decimal_places=2, default=0)
    notes = models.TextField(blank=True)
    order = models.PositiveIntegerField(default=0)

    class Meta:
        ordering = ["order", "id"]
        indexes = [models.Index(fields=["stage", "order"])]


class EventVendorRequirementTemplate(models.Model):
    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    stage = models.ForeignKey(EventStageTemplate, on_delete=models.CASCADE, related_name="vendor_requirements")
    category = models.CharField(max_length=120)
    title = models.CharField(max_length=300)
    description = models.TextField(blank=True)
    minimum_budget = models.DecimalField(max_digits=14, decimal_places=2, blank=True, null=True)
    maximum_budget = models.DecimalField(max_digits=14, decimal_places=2, blank=True, null=True)
    order = models.PositiveIntegerField(default=0)

    class Meta:
        ordering = ["order", "id"]
        indexes = [models.Index(fields=["stage", "category"])]


class EventQuestionTemplate(models.Model):
    class AnswerType(models.TextChoices):
        TEXT = "text", "Text"
        BOOLEAN = "boolean", "Yes/No"
        NUMBER = "number", "Number"
        DATE = "date", "Date"

    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    stage = models.ForeignKey(EventStageTemplate, on_delete=models.CASCADE, related_name="questions")
    prompt = models.CharField(max_length=500)
    help_text = models.TextField(blank=True)
    answer_type = models.CharField(max_length=20, choices=AnswerType.choices, default=AnswerType.TEXT)
    is_required = models.BooleanField(default=False)
    order = models.PositiveIntegerField(default=0)

    class Meta:
        ordering = ["order", "id"]
        indexes = [models.Index(fields=["stage", "order"])]


class EventStage(models.Model):
    class Status(models.TextChoices):
        NOT_STARTED = "not_started", "Not started"
        IN_PROGRESS = "in_progress", "In progress"
        COMPLETED = "completed", "Completed"

    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    event = models.ForeignKey(Event, on_delete=models.CASCADE, related_name="workspace_stages")
    template_stage = models.ForeignKey(EventStageTemplate, on_delete=models.SET_NULL, blank=True, null=True)
    name = models.CharField(max_length=200)
    slug = models.SlugField(max_length=120)
    description = models.TextField(blank=True)
    status = models.CharField(max_length=20, choices=Status.choices, default=Status.NOT_STARTED)
    order = models.PositiveIntegerField(default=0)
    created_at = models.DateTimeField(default=timezone.now)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        ordering = ["order", "id"]
        constraints = [models.UniqueConstraint(fields=["event", "slug"], name="unique_event_stage_slug")]
        indexes = [models.Index(fields=["event", "order"]), models.Index(fields=["event", "status"])]


class EventTask(models.Model):
    class Status(models.TextChoices):
        PENDING = "pending", "Pending"
        IN_PROGRESS = "in_progress", "In progress"
        COMPLETED = "completed", "Completed"
        BLOCKED = "blocked", "Blocked"

    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    event = models.ForeignKey(Event, on_delete=models.CASCADE, related_name="workspace_tasks")
    stage = models.ForeignKey(EventStage, on_delete=models.CASCADE, related_name="tasks")
    title = models.CharField(max_length=300)
    description = models.TextField(blank=True)
    status = models.CharField(max_length=20, choices=Status.choices, default=Status.PENDING)
    due_date = models.DateField(blank=True, null=True)
    assigned_to = models.CharField(max_length=200, blank=True)
    notes = models.TextField(blank=True)
    order = models.PositiveIntegerField(default=0)
    created_at = models.DateTimeField(default=timezone.now)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        ordering = ["stage__order", "order", "id"]
        indexes = [models.Index(fields=["event", "status"]), models.Index(fields=["event", "due_date"]), models.Index(fields=["stage", "order"])]


class EventBudgetItem(models.Model):
    class Status(models.TextChoices):
        PLANNED = "planned", "Planned"
        QUOTED = "quoted", "Quoted"
        PAID = "paid", "Paid"

    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    event = models.ForeignKey(Event, on_delete=models.CASCADE, related_name="workspace_budget_items")
    stage = models.ForeignKey(EventStage, on_delete=models.CASCADE, related_name="budget_items")
    category = models.CharField(max_length=120)
    item = models.CharField(max_length=300)
    estimated_cost = models.DecimalField(max_digits=14, decimal_places=2, default=0)
    actual_cost = models.DecimalField(max_digits=14, decimal_places=2, blank=True, null=True)
    status = models.CharField(max_length=20, choices=Status.choices, default=Status.PLANNED)
    notes = models.TextField(blank=True)
    order = models.PositiveIntegerField(default=0)
    created_at = models.DateTimeField(default=timezone.now)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        ordering = ["stage__order", "order", "id"]
        indexes = [models.Index(fields=["event", "category"]), models.Index(fields=["event", "status"]), models.Index(fields=["stage", "order"])]


class EventVendorRequirement(models.Model):
    class Status(models.TextChoices):
        OPEN = "open", "Open"
        SHORTLISTED = "shortlisted", "Shortlisted"
        BOOKED = "booked", "Booked"

    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    event = models.ForeignKey(Event, on_delete=models.CASCADE, related_name="workspace_vendor_requirements")
    stage = models.ForeignKey(EventStage, on_delete=models.CASCADE, related_name="vendor_requirements")
    assigned_vendor = models.ForeignKey("vendors.VendorProfile", on_delete=models.SET_NULL, blank=True, null=True)
    category = models.CharField(max_length=120)
    title = models.CharField(max_length=300)
    description = models.TextField(blank=True)
    minimum_budget = models.DecimalField(max_digits=14, decimal_places=2, blank=True, null=True)
    maximum_budget = models.DecimalField(max_digits=14, decimal_places=2, blank=True, null=True)
    status = models.CharField(max_length=20, choices=Status.choices, default=Status.OPEN)
    notes = models.TextField(blank=True)
    order = models.PositiveIntegerField(default=0)
    created_at = models.DateTimeField(default=timezone.now)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        ordering = ["stage__order", "order", "id"]
        indexes = [models.Index(fields=["event", "status"]), models.Index(fields=["event", "category"]), models.Index(fields=["stage", "order"])]


class EventQuestionAnswer(models.Model):
    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    event = models.ForeignKey(Event, on_delete=models.CASCADE, related_name="workspace_answers")
    stage = models.ForeignKey(EventStage, on_delete=models.CASCADE, related_name="answers")
    question_template = models.ForeignKey(EventQuestionTemplate, on_delete=models.SET_NULL, blank=True, null=True)
    question = models.CharField(max_length=500)
    answer = models.JSONField(blank=True, null=True)
    created_at = models.DateTimeField(default=timezone.now)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        ordering = ["stage__order", "question"]
        indexes = [models.Index(fields=["event", "stage"])]


class EventTimelineItem(models.Model):
    class Status(models.TextChoices):
        PLANNED = "planned", "Planned"
        COMPLETED = "completed", "Completed"

    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    event = models.ForeignKey(Event, on_delete=models.CASCADE, related_name="workspace_timeline_items")
    stage = models.ForeignKey(EventStage, on_delete=models.CASCADE, related_name="timeline_items", blank=True, null=True)
    title = models.CharField(max_length=300)
    scheduled_at = models.DateTimeField(blank=True, null=True)
    location = models.CharField(max_length=300, blank=True)
    description = models.TextField(blank=True)
    status = models.CharField(max_length=20, choices=Status.choices, default=Status.PLANNED)
    order = models.PositiveIntegerField(default=0)
    created_at = models.DateTimeField(default=timezone.now)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        ordering = ["scheduled_at", "order", "id"]
        indexes = [models.Index(fields=["event", "scheduled_at"]), models.Index(fields=["event", "status"])]


class EventDocument(models.Model):
    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    event = models.ForeignKey(Event, on_delete=models.CASCADE, related_name="workspace_documents")
    stage = models.ForeignKey(EventStage, on_delete=models.CASCADE, related_name="documents", blank=True, null=True)
    title = models.CharField(max_length=300)
    document_type = models.CharField(max_length=100, blank=True)
    file_url = models.URLField()
    notes = models.TextField(blank=True)
    created_at = models.DateTimeField(default=timezone.now)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        ordering = ["-created_at"]
        indexes = [models.Index(fields=["event", "document_type"])]


class EventActivityLog(models.Model):
    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    event = models.ForeignKey(Event, on_delete=models.CASCADE, related_name="workspace_activity")
    actor = models.ForeignKey(User, on_delete=models.SET_NULL, blank=True, null=True)
    action = models.CharField(max_length=100)
    entity_type = models.CharField(max_length=100, blank=True)
    entity_id = models.UUIDField(blank=True, null=True)
    details = models.JSONField(default=dict, blank=True)
    created_at = models.DateTimeField(default=timezone.now)

    class Meta:
        ordering = ["-created_at"]
        indexes = [models.Index(fields=["event", "-created_at"]), models.Index(fields=["event", "action"])]
