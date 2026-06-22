from datetime import date

import pytest
from django.core.management import call_command
from django.urls import reverse
from rest_framework.test import APIClient

from django_app.events.models import (
    Event,
    EventActivityLog,
    EventBudgetItemTemplate,
    EventStageTemplate,
    EventTask,
    EventTaskTemplate,
    EventTemplate,
)
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
    template = EventTemplate.objects.create(
        slug="rwanda-wedding-workspace",
        name="Rwanda Wedding Workspace",
        event_type="wedding",
        country="Rwanda",
    )
    stage = EventStageTemplate.objects.create(template=template, name="Civil Marriage", slug="civil-marriage", order=1)
    EventTaskTemplate.objects.create(stage=stage, title="Book civil ceremony", days_before_event=30)
    EventBudgetItemTemplate.objects.create(stage=stage, category="Civil", item="Marriage certificate", estimated_cost=2400)
    return template


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
    assert event.workspace_stages.count() == 1
    assert event.workspace_tasks.get().due_date == date(2027, 7, 21)


def test_workspace_summary_and_task_update_log_activity(planner_client, wedding_template):
    planner, client = planner_client
    event = create_event(planner=planner, country="Rwanda")
    summary = client.get(reverse("event-workspace", kwargs={"event_id": event.id}))

    assert summary.status_code == 200
    assert summary.data["task_summary"] == {"total": 1, "completed": 0}
    assert [stage["name"] for stage in summary.data["stages"]] == ["Civil Marriage"]

    task = EventTask.objects.get(event=event)
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
    task = EventTask.objects.get(event=event)

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
