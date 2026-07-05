from datetime import date

import pytest
from django.core.management import call_command
from django.core.exceptions import ImproperlyConfigured
from django.urls import reverse
from rest_framework.test import APIClient

from django_app.events.models import (
    Event,
    EventActivityLog,
    EventBudgetItem,
    EventBudgetItemTemplate,
    EventQuestionAnswer,
    EventStageTemplate,
    EventTask,
    EventTaskTemplate,
    EventTemplate,
    EventVendorRequirement,
    EventVendorRequirementTemplate,
)
from django_app.events.template_seeders.rwanda_wedding import STAGES, ensure_rwanda_wedding_template
from django_app.events.workspace_service import generate_event_workspace
from django_app.vendors.models import ServicePackage
from tests.factories import create_event, create_service_package, create_user, create_vendor_profile

pytestmark = pytest.mark.django_db


@pytest.fixture
def planner_client():
    planner = create_user(role="planner")
    client = APIClient()
    client.force_authenticate(user=planner)
    return planner, client


@pytest.fixture
def wedding_template():
    return ensure_rwanda_wedding_template()


def test_wedding_create_aliases_generate_workspace(planner_client, wedding_template):
    planner, client = planner_client
    response = client.post(
        reverse("event-list"),
        {
            "title": "Our Wedding",
            "event_type": "wedding",
            "event_date": "2027-08-20",
            "location": "Kigali",
            "guest_count": 120,
            "country": "Rwanda",
        },
        format="json",
    )

    assert response.status_code == 201
    event = Event.objects.get(planner=planner)
    assert event.name == "Our Wedding"
    assert event.venue == "Kigali"
    assert event.expected_guests == 120
    assert event.workspace_stages.count() == 6
    assert list(event.workspace_stages.order_by("order").values_list("name", flat=True)) == [stage[0] for stage in STAGES]
    assert event.workspace_tasks.exists()
    assert event.workspace_budget_items.exists()
    assert event.workspace_vendor_requirements.exists()
    assert event.workspace_answers.exists()
    assert event.workspace_tasks.order_by("due_date").first().due_date <= date(2027, 8, 13)


def test_workspace_summary_and_task_update_log_activity(planner_client, wedding_template):
    planner, client = planner_client
    event = create_event(planner=planner, country="Rwanda")
    summary = client.get(reverse("event-workspace", kwargs={"event_id": event.id}))

    assert summary.status_code == 200
    assert summary.data["task_summary"]["total"] == event.workspace_tasks.count()
    assert summary.data["task_summary"]["completed"] == 0
    assert [stage["name"] for stage in summary.data["stages"]] == [stage[0] for stage in STAGES]

    task = EventTask.objects.filter(event=event).order_by("stage__order", "order").first()
    update = client.patch(
        reverse("event-workspace-task-detail", kwargs={"event_id": event.id, "object_id": task.id}),
        {"status": "completed"},
        format="json",
    )

    assert update.status_code == 200
    assert EventActivityLog.objects.filter(event=event, action="eventtask_updated", actor=planner).exists()


def test_workspace_child_lookup_is_scoped_to_owner(planner_client, wedding_template):
    owner = create_user(role="planner")
    event = create_event(planner=owner, country="Rwanda")
    owner_client = APIClient()
    owner_client.force_authenticate(user=owner)
    owner_client.get(reverse("event-workspace", kwargs={"event_id": event.id}))
    task = EventTask.objects.filter(event=event).order_by("stage__order", "order").first()

    _, other_client = planner_client
    response = other_client.patch(
        reverse("event-workspace-task-detail", kwargs={"event_id": event.id, "object_id": task.id}),
        {"status": "completed"},
        format="json",
    )

    assert response.status_code == 404
    task.refresh_from_db()
    assert task.status == "pending"


def test_vendor_recommendations_are_approved_and_match_category_location(planner_client, wedding_template):
    planner, client = planner_client
    event = create_event(planner=planner, venue="Kigali", country="Rwanda")
    approved = create_vendor_profile(status="approved", category="photography", service_area="Kigali and Musanze")
    draft = create_vendor_profile(status="draft", category="photography", service_area="Kigali")
    create_service_package(vendor=approved, approval_status=ServicePackage.ApprovalStatus.APPROVED, price=100000)
    create_service_package(vendor=draft, approval_status=ServicePackage.ApprovalStatus.APPROVED, price=50000)

    response = client.get(
        reverse("event-workspace-vendor-recommendations", kwargs={"event_id": event.id}),
        {"category": "photography"},
    )

    assert response.status_code == 200
    assert [item["id"] for item in response.data["results"]] == [str(approved.id)]


def test_seed_command_is_idempotent():
    call_command("seed_rwanda_wedding_template")
    call_command("seed_rwanda_wedding_template")

    template = EventTemplate.objects.get(slug="rwanda-wedding-workspace")
    assert template.stages.count() == 6
    assert EventTemplate.objects.filter(slug="rwanda-wedding-workspace").count() == 1


def test_ensure_rwanda_wedding_template_creates_official_template():
    template = ensure_rwanda_wedding_template()

    assert template.event_type == "wedding"
    assert template.country == "Rwanda"
    assert template.is_active is True
    assert list(template.stages.order_by("order").values_list("name", flat=True)) == [stage[0] for stage in STAGES]
    assert EventTaskTemplate.objects.filter(stage__template=template).exists()
    assert EventBudgetItemTemplate.objects.filter(stage__template=template).exists()
    assert EventVendorRequirementTemplate.objects.filter(stage__template=template).exists()


def test_workspace_summary_generates_missing_wedding_workspace(planner_client, wedding_template):
    planner, client = planner_client
    event = create_event(planner=planner, country="Rwanda")

    response = client.get(reverse("event-workspace", kwargs={"event_id": event.id}))

    assert response.status_code == 200
    assert event.workspace_stages.count() == 6
    assert EventTask.objects.filter(event=event).exists()
    assert EventBudgetItem.objects.filter(event=event).exists()
    assert EventVendorRequirement.objects.filter(event=event).exists()
    assert EventQuestionAnswer.objects.filter(event=event).exists()


def test_generate_event_workspace_raises_for_rwanda_wedding_missing_template(monkeypatch):
    event = create_event(country="Rwanda")

    def missing_template():
        raise ImproperlyConfigured("Rwanda wedding template seed files are missing from deployment.")

    monkeypatch.setattr("django_app.events.workspace_service.ensure_rwanda_wedding_template", missing_template)

    with pytest.raises(ImproperlyConfigured):
        generate_event_workspace(event)

    assert event.workspace_stages.count() == 0


def test_wedding_event_creation_rolls_back_when_workspace_clone_fails(planner_client, monkeypatch):
    planner, client = planner_client

    def clone_failure(event):
        raise ImproperlyConfigured("Rwanda wedding template seed files are missing from deployment.")

    monkeypatch.setattr("django_app.events.views.generate_event_workspace", clone_failure)
    response = client.post(
        reverse("event-list"),
        {
            "name": "Broken Wedding",
            "event_type": "wedding",
            "event_date": "2027-08-20",
            "country": "Rwanda",
            "total_budget": "1000.00",
        },
        format="json",
    )

    assert response.status_code == 500
    assert response.data["code"] == "rwanda_wedding_template_missing"
    assert not Event.objects.filter(planner=planner, name="Broken Wedding").exists()


def test_non_wedding_event_creation_does_not_require_wedding_template(planner_client, monkeypatch):
    planner, client = planner_client

    def missing_template():
        raise ImproperlyConfigured("Rwanda wedding template seed files are missing from deployment.")

    monkeypatch.setattr("django_app.events.workspace_service.ensure_rwanda_wedding_template", missing_template)
    response = client.post(
        reverse("event-list"),
        {
            "name": "Corporate Retreat",
            "event_type": "corporate",
            "event_date": "2027-08-20",
            "country": "Rwanda",
            "total_budget": "1000.00",
        },
        format="json",
    )

    assert response.status_code == 201
    event = Event.objects.get(planner=planner, name="Corporate Retreat")
    assert event.workspace_stages.count() == 0


def test_backfill_wedding_workspaces_is_idempotent(planner_client, wedding_template):
    planner, _ = planner_client
    event = create_event(planner=planner, country="Rwanda")

    call_command("backfill_wedding_workspaces")
    call_command("backfill_wedding_workspaces")

    assert event.workspace_stages.count() == 6
    assert EventActivityLog.objects.filter(event=event, action="workspace_generated").count() == 1
