import uuid
import pytest
from django.urls import reverse
from rest_framework.test import APIClient

from django_app.identity.models import User as DjangoUser
from django_app.events.models import Event as DjangoEvent

pytestmark = pytest.mark.django_db


class TestEventViews:
    @pytest.fixture(autouse=True)
    def setup(self):
        self.client = APIClient()

    def test_create_event_authenticated(self):
        user = DjangoUser.objects.create_user(
            email="planner@test.com",
            password="testpass123",
            first_name="Test",
            last_name="Planner",
            role="planner",
        )
        self.client.force_authenticate(user=user)
        url = reverse("event-list")
        data = {
            "name": "Corporate Retreat",
            "event_type": "corporate",
            "event_date": "2025-09-10",
            "venue": "Conference Center",
            "expected_guests": 50,
            "total_budget": "5000.00",
        }
        response = self.client.post(url, data, format="json")
        assert response.status_code == 201
        assert DjangoEvent.objects.count() == 1

    def test_list_events(self):
        user = DjangoUser.objects.create_user(
            email="planner@test.com",
            password="testpass123",
            first_name="Test",
            last_name="Planner",
            role="planner",
        )
        DjangoEvent.objects.create(
            planner=user, name="Event1", event_type="wedding", event_date="2025-01-01"
        )
        DjangoEvent.objects.create(
            planner=user, name="Event2", event_type="travel", event_date="2025-02-01"
        )
        self.client.force_authenticate(user=user)
        url = reverse("event-list")
        response = self.client.get(url)
        assert response.status_code == 200
        assert len(response.data) == 2

    def test_get_event_detail(self):
        user = DjangoUser.objects.create_user(
            email="planner@test.com",
            password="testpass123",
            first_name="Test",
            last_name="Planner",
            role="planner",
        )
        event = DjangoEvent.objects.create(
            planner=user,
            name="Event1",
            event_type="wedding",
            event_date="2025-01-01",
        )
        self.client.force_authenticate(user=user)
        url = reverse("event-detail", kwargs={"event_id": event.id})
        response = self.client.get(url)
        assert response.status_code == 200
        assert response.data["id"] == str(event.id)
        assert response.data["planner_id"] == str(user.id)

    def test_list_checklists_for_event(self):
        user = DjangoUser.objects.create_user(
            email="planner@test.com",
            password="testpass123",
            first_name="Test",
            last_name="Planner",
            role="planner",
        )
        event = DjangoEvent.objects.create(
            planner=user,
            name="Event1",
            event_type="wedding",
            event_date="2025-01-01",
        )
        event.checklists.create(name="Venue checklist")
        self.client.force_authenticate(user=user)
        url = reverse("event-checklists", kwargs={"event_id": event.id})
        response = self.client.get(url)
        assert response.status_code == 200
        assert len(response.data) == 1
        assert response.data[0]["name"] == "Venue checklist"

    def test_list_budget_lines_for_event(self):
        user = DjangoUser.objects.create_user(
            email="planner@test.com",
            password="testpass123",
            first_name="Test",
            last_name="Planner",
            role="planner",
        )
        event = DjangoEvent.objects.create(
            planner=user,
            name="Event1",
            event_type="wedding",
            event_date="2025-01-01",
        )
        event.budget_lines.create(category="venue", description="Main hall", estimated_cost=1000)
        self.client.force_authenticate(user=user)
        url = reverse("event-budget-lines", kwargs={"event_id": event.id})
        response = self.client.get(url)
        assert response.status_code == 200
        assert len(response.data) == 1
        assert response.data[0]["description"] == "Main hall"

    def test_list_guests_for_event(self):
        user = DjangoUser.objects.create_user(
            email="planner@test.com",
            password="testpass123",
            first_name="Test",
            last_name="Planner",
            role="planner",
        )
        event = DjangoEvent.objects.create(
            planner=user,
            name="Event1",
            event_type="wedding",
            event_date="2025-01-01",
        )
        event.guests.create(full_name="Jane Doe", email="jane@example.com")
        self.client.force_authenticate(user=user)
        url = reverse("event-guests", kwargs={"event_id": event.id})
        response = self.client.get(url)
        assert response.status_code == 200
        assert len(response.data) == 1
        assert response.data[0]["full_name"] == "Jane Doe"

    def test_list_timeline_blocks_for_event(self):
        user = DjangoUser.objects.create_user(
            email="planner@test.com",
            password="testpass123",
            first_name="Test",
            last_name="Planner",
            role="planner",
        )
        event = DjangoEvent.objects.create(
            planner=user,
            name="Event1",
            event_type="wedding",
            event_date="2025-01-01",
        )
        event.timeline_blocks.create(
            title="Ceremony",
            start_time="2025-01-01T10:00:00Z",
            end_time="2025-01-01T11:00:00Z",
        )
        self.client.force_authenticate(user=user)
        url = reverse("event-timeline-blocks", kwargs={"event_id": event.id})
        response = self.client.get(url)
        assert response.status_code == 200
        assert len(response.data) == 1
        assert response.data[0]["title"] == "Ceremony"

    def test_unauthenticated_access_returns_401(self):
        url = reverse("event-list")
        response = self.client.get(url)
        assert response.status_code == 401
