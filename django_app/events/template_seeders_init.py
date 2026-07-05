from __future__ import annotations

from decimal import Decimal

from django.db import transaction

from django_app.events.models import (
    Event,
    EventBudgetItemTemplate,
    EventQuestionTemplate,
    EventStageTemplate,
    EventTaskTemplate,
    EventTemplate,
    EventVendorRequirementTemplate,
)

TEMPLATE_SLUG = "rwanda-wedding-workspace"

STAGES: tuple[tuple[str, str], ...] = (
    ("Proposal / Engagement planning", "proposal-engagement"),
    ("Gufata Irembo", "gufata-irembo"),
    ("Civil Marriage", "civil-marriage"),
    ("Gusaba / Gukwa / Dote", "gusaba-gukwa-dote"),
    ("Church Wedding", "church-wedding"),
    ("Wedding Reception", "wedding-reception"),
)

DEFAULT_ROWS: dict[str, list[tuple[str, str, Decimal, str]]] = {
    "proposal-engagement": [
        ("planning", "Engagement planning meeting", Decimal("50000"), "Confirm families, date, and expectations."),
        ("photography", "Proposal photography", Decimal("150000"), "Capture engagement memories."),
        ("decor", "Simple engagement decoration", Decimal("100000"), "Prepare a small setup."),
    ],
    "gufata-irembo": [
        ("venue", "Family meeting venue", Decimal("200000"), "Reserve location for Gufata Irembo."),
        ("catering", "Food and drinks", Decimal("350000"), "Plan refreshments for families."),
        ("photography", "Photo and video coverage", Decimal("250000"), "Document the ceremony."),
    ],
    "civil-marriage": [
        ("documents", "Civil marriage documents", Decimal("50000"), "Prepare required documents."),
        ("transportation", "Transport to civil office", Decimal("80000"), "Arrange movement for couple and witnesses."),
        ("attire", "Civil ceremony attire", Decimal("200000"), "Prepare formal attire."),
    ],
    "gusaba-gukwa-dote": [
        ("venue", "Traditional ceremony venue", Decimal("500000"), "Book ceremony location."),
        ("catering", "Traditional ceremony catering", Decimal("900000"), "Food and drinks for guests."),
        ("entertainment", "Traditional dance group", Decimal("250000"), "Book cultural entertainment."),
    ],
    "church-wedding": [
        ("venue", "Ceremony support", Decimal("150000"), "Confirm ceremony requirements."),
        ("decor", "Flowers and decoration", Decimal("300000"), "Confirm allowed decoration."),
        ("photography", "Ceremony photo and video", Decimal("350000"), "Capture ceremony moments."),
    ],
    "wedding-reception": [
        ("venue", "Reception hall", Decimal("1200000"), "Book reception venue."),
        ("catering", "Reception catering", Decimal("2500000"), "Food and drinks for guests."),
        ("entertainment", "DJ / sound / MC", Decimal("600000"), "Book reception entertainment and protocol."),
    ],
}

VENDOR_CATEGORIES = {"photography", "catering", "decor", "venue", "entertainment", "transportation", "attire"}


def _required_stage_names() -> list[str]:
    return [name for name, _ in STAGES]


def _template_has_required_stages(template: EventTemplate) -> bool:
    stage_names = list(template.stages.order_by("order").values_list("name", flat=True))
    return stage_names == _required_stage_names()


@transaction.atomic
def seed_rwanda_wedding_template() -> dict[str, int | str]:
    template, _ = EventTemplate.objects.update_or_create(
        slug=TEMPLATE_SLUG,
        defaults={
            "name": "Rwanda Wedding Workspace",
            "event_type": Event.EventType.WEDDING,
            "country": "Rwanda",
            "description": "A six-stage Rwanda wedding planning workspace.",
            "version": 1,
            "is_active": True,
        },
    )
    template.stages.all().delete()
    totals: dict[str, int | str] = {
        "slug": TEMPLATE_SLUG,
        "stages": 0,
        "tasks": 0,
        "budget_items": 0,
        "vendor_requirements": 0,
        "questions": 0,
    }

    for stage_order, (name, slug) in enumerate(STAGES, start=1):
        stage = EventStageTemplate.objects.create(
            template=template,
            name=name,
            slug=slug,
            description=f"Plan and track the {name.lower()} stage.",
            order=stage_order,
        )
        totals["stages"] = int(totals["stages"]) + 1

        rows = DEFAULT_ROWS[slug]
        for order, (category, item, estimate, notes) in enumerate(rows, start=1):
            EventBudgetItemTemplate.objects.create(
                stage=stage,
                category=category,
                item=item,
                estimated_cost=estimate,
                notes=notes,
                order=order,
            )
            EventTaskTemplate.objects.create(
                stage=stage,
                title=f"Confirm {item}",
                description=notes,
                days_before_event=max(7, (7 - stage_order) * 30),
                order=order,
            )
            totals["budget_items"] = int(totals["budget_items"]) + 1
            totals["tasks"] = int(totals["tasks"]) + 1

        for order, category in enumerate(sorted({row[0] for row in rows if row[0] in VENDOR_CATEGORIES}), start=1):
            maximum_budget = sum(row[2] for row in rows if row[0] == category)
            EventVendorRequirementTemplate.objects.create(
                stage=stage,
                category=category,
                title=f"Find a {category.replace('_', ' ')} vendor",
                maximum_budget=maximum_budget or None,
                order=order,
            )
            totals["vendor_requirements"] = int(totals["vendor_requirements"]) + 1

        questions = [
            f"Who is responsible for the {name.lower()} stage?",
            f"Is the date and location confirmed for {name.lower()}?",
        ]
        for order, prompt in enumerate(questions, start=1):
            EventQuestionTemplate.objects.create(stage=stage, prompt=prompt, order=order)
            totals["questions"] = int(totals["questions"]) + 1

    return totals


@transaction.atomic
def ensure_rwanda_wedding_template() -> EventTemplate:
    template = (
        EventTemplate.objects.filter(
            slug=TEMPLATE_SLUG,
            event_type=Event.EventType.WEDDING,
            country__iexact="Rwanda",
            is_active=True,
        )
        .prefetch_related("stages")
        .order_by("-version", "-updated_at")
        .first()
    )
    if template and _template_has_required_stages(template):
        return template
    seed_rwanda_wedding_template()
    template = EventTemplate.objects.get(slug=TEMPLATE_SLUG)
    if not _template_has_required_stages(template):
        raise RuntimeError("Rwanda wedding template could not be prepared.")
    return template
