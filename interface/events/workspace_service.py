from datetime import timedelta

from django.db import transaction
from django.db.models import Prefetch

from .models import (
    Event,
    EventActivityLog,
    EventBudgetItem,
    EventQuestionAnswer,
    EventStage,
    EventStageTemplate,
    EventTask,
    EventTemplate,
    EventVendorRequirement,
)
from .template_seeders.rwanda_wedding import ensure_rwanda_wedding_template


@transaction.atomic
def generate_event_workspace(event: Event) -> list[EventStage]:
    existing = list(event.workspace_stages.order_by("order"))
    if existing:
        return existing

    if event.event_type == Event.EventType.WEDDING and event.country.lower() == "rwanda":
        template = ensure_rwanda_wedding_template()
        template_filter = {"id": template.id}
    else:
        template_filter = {
            "event_type": event.event_type,
            "country__iexact": event.country,
            "is_active": True,
        }

    template = (
        EventTemplate.objects.filter(**template_filter)
        .prefetch_related(
            Prefetch(
                "stages",
                queryset=EventStageTemplate.objects.prefetch_related(
                    "tasks", "budget_items", "vendor_requirements", "questions"
                ).order_by("order"),
            )
        )
        .order_by("-version", "-updated_at")
        .first()
    )
    if not template:
        return []

    generated_stages = []
    for stage_template in template.stages.all():
        stage = EventStage.objects.create(
            event=event,
            template_stage=stage_template,
            name=stage_template.name,
            slug=stage_template.slug,
            description=stage_template.description,
            order=stage_template.order,
        )
        generated_stages.append(stage)

        EventTask.objects.bulk_create(
            [
                EventTask(
                    event=event,
                    stage=stage,
                    title=item.title,
                    description=item.description,
                    due_date=(event.event_date - timedelta(days=item.days_before_event))
                    if item.days_before_event is not None
                    else None,
                    order=item.order,
                )
                for item in stage_template.tasks.all()
            ]
        )
        EventBudgetItem.objects.bulk_create(
            [
                EventBudgetItem(
                    event=event,
                    stage=stage,
                    category=item.category,
                    item=item.item,
                    estimated_cost=item.estimated_cost,
                    notes=item.notes,
                    order=item.order,
                )
                for item in stage_template.budget_items.all()
            ]
        )
        EventVendorRequirement.objects.bulk_create(
            [
                EventVendorRequirement(
                    event=event,
                    stage=stage,
                    category=item.category,
                    title=item.title,
                    description=item.description,
                    minimum_budget=item.minimum_budget,
                    maximum_budget=item.maximum_budget,
                    order=item.order,
                )
                for item in stage_template.vendor_requirements.all()
            ]
        )
        EventQuestionAnswer.objects.bulk_create(
            [
                EventQuestionAnswer(
                    event=event,
                    stage=stage,
                    question_template=item,
                    question=item.prompt,
                )
                for item in stage_template.questions.all()
            ]
        )

    EventActivityLog.objects.create(
        event=event,
        actor=event.planner,
        action="workspace_generated",
        entity_type="event",
        entity_id=event.id,
        details={"template": template.slug, "template_version": template.version},
    )
    return generated_stages


def log_workspace_activity(event, actor, action, instance, details=None):
    return EventActivityLog.objects.create(
        event=event,
        actor=actor,
        action=action,
        entity_type=instance._meta.model_name,
        entity_id=instance.id,
        details=details or {},
    )
