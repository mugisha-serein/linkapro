import pytest
from django.urls import reverse
from rest_framework.test import APIClient

from django_app.events.models import EventVendorAssignment
from tests.factories import create_event, create_event_vendor_assignment, create_user, create_vendor_profile

pytestmark = pytest.mark.django_db


def test_planner_can_add_and_list_event_vendor_assignment():
    client = APIClient()
    planner = create_user(role="planner")
    event = create_event(planner=planner)
    vendor = create_vendor_profile(status="approved")
    client.force_authenticate(user=planner)

    url = reverse("event-vendors", kwargs={"event_id": event.id})
    response = client.post(url, {"vendor_id": str(vendor.id)}, format="json")

    assert response.status_code == 201
    assert response.data["event_id"] == str(event.id)
    assert response.data["vendor_id"] == str(vendor.id)
    assert response.data["business_name"] == vendor.business_name

    list_response = client.get(url)

    assert list_response.status_code == 200
    assert len(list_response.data) == 1
    assert list_response.data[0]["vendor_id"] == str(vendor.id)


def test_duplicate_event_vendor_assignment_returns_existing_row():
    client = APIClient()
    planner = create_user(role="planner")
    event = create_event(planner=planner)
    vendor = create_vendor_profile(status="approved")
    existing = create_event_vendor_assignment(event=event, vendor=vendor)
    client.force_authenticate(user=planner)

    url = reverse("event-vendors", kwargs={"event_id": event.id})
    response = client.post(url, {"vendor_id": str(vendor.id)}, format="json")

    assert response.status_code == 200
    assert response.data["id"] == str(existing.id)
    assert EventVendorAssignment.objects.filter(event=event, vendor=vendor).count() == 1


def test_planner_can_update_and_remove_event_vendor_assignment():
    client = APIClient()
    planner = create_user(role="planner")
    assignment = create_event_vendor_assignment(event=create_event(planner=planner))
    client.force_authenticate(user=planner)

    url = reverse(
        "event-vendor-detail",
        kwargs={"event_id": assignment.event_id, "assignment_id": assignment.id},
    )
    update_response = client.patch(url, {"status": "booked", "notes": "Confirmed"}, format="json")

    assert update_response.status_code == 200
    assert update_response.data["status"] == "booked"
    assert update_response.data["notes"] == "Confirmed"

    delete_response = client.delete(url)

    assert delete_response.status_code == 204
    assert not EventVendorAssignment.objects.filter(id=assignment.id).exists()


def test_planner_cannot_access_another_planners_event_vendor_assignments():
    client = APIClient()
    owner = create_user(role="planner")
    other = create_user(role="planner")
    event = create_event(planner=owner)
    assignment = create_event_vendor_assignment(event=event)
    client.force_authenticate(user=other)

    list_url = reverse("event-vendors", kwargs={"event_id": event.id})
    detail_url = reverse(
        "event-vendor-detail",
        kwargs={"event_id": event.id, "assignment_id": assignment.id},
    )

    assert client.get(list_url).status_code == 404
    assert client.delete(detail_url).status_code == 404
