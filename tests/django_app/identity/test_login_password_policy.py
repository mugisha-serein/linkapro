import pytest
from django.urls import reverse
from rest_framework.test import APIClient

from django_app.identity.models import User


pytestmark = pytest.mark.django_db(transaction=True)


class TestLoginPasswordPolicy:
    def setup_method(self):
        self.client = APIClient()

    def test_login_allows_existing_password_that_does_not_match_current_strength_policy(self):
        User.objects.create_user(
            email="legacy-weak@example.com",
            password="lowercase1",
            first_name="Legacy",
            last_name="User",
            role="planner",
        )

        response = self.client.post(
            reverse("login"),
            {"email": "legacy-weak@example.com", "password": "lowercase1"},
            format="json",
        )

        assert response.status_code == 200
        assert response.data["success"] is True
        assert response.data["code"] == "login_completed"
        assert "access" in response.data["data"]
        assert "refresh_token" in response.cookies

    def test_wrong_login_password_that_fails_strength_policy_returns_invalid_credentials_not_500(self):
        User.objects.create_user(
            email="legacy-wrong@example.com",
            password="CorrectPass1",
            first_name="Legacy",
            last_name="Wrong",
            role="planner",
        )

        response = self.client.post(
            reverse("login"),
            {"email": "legacy-wrong@example.com", "password": "lowercase1"},
            format="json",
        )

        assert response.status_code == 401
        assert response.data["success"] is False
        assert response.data["code"] == "invalid_credentials"
