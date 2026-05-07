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

    def test_unauthenticated_access_returns_401(self):
        url = reverse("event-list")
        response = self.client.get(url)
        assert response.status_code == 401
