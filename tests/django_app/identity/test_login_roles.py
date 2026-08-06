import logging
import pytest
from django.urls import reverse
from rest_framework.test import APIClient
from interface.identity.models import User as DjangoUser

pytestmark = pytest.mark.django_db(transaction=True)


class TestDjangoAppIdentityLogin:
    @pytest.fixture(autouse=True)
    def setup(self):
        self.client = APIClient()

    @pytest.mark.parametrize("role", ["admin", "vendor", "planner"])
    def test_login_endpoint_succeeds_for_all_roles(self, role):
        user = DjangoUser.objects.create_user(
            email=f"{role}-test@example.com",
            password="StrongPass1!",
            first_name=role.title(),
            last_name="User",
            role=role,
            is_active=True,
            is_verified=True,
            is_staff=(role == "admin"),
        )

        response = self.client.post(
            reverse("login"),
            {"email": f"{role}-test@example.com", "password": "StrongPass1!"},
            format="json",
        )

        assert response.status_code == 200
        assert response.data["success"] is True
        assert response.data["code"] == "login_completed"
        assert "access" in response.data["data"]
        assert response.data["data"]["user"]["role"] == role
        assert response.data["data"]["user"]["id"] == str(user.id)
        assert "refresh_token" in response.cookies

    def test_login_endpoint_logs_user_not_found_event(self, caplog):
        with caplog.at_level(logging.INFO):
            response = self.client.post(
                reverse("login"),
                {"email": "missing-user@example.com", "password": "StrongPass1!"},
                format="json",
            )

        assert response.status_code == 401
        assert response.data["code"] == "invalid_credentials"
        assert any(record.message == "user_not_found" for record in caplog.records)
        assert not any(record.message == "identity_authentication_failed" for record in caplog.records)

    def test_login_endpoint_logs_password_mismatch_event(self, caplog):
        DjangoUser.objects.create_user(
            email="vendor-mismatch@example.com",
            password="CorrectPass1!",
            first_name="Vendor",
            last_name="Mismatch",
            role="vendor",
            is_active=True,
            is_verified=True,
        )

        with caplog.at_level(logging.INFO):
            response = self.client.post(
                reverse("login"),
                {"email": "vendor-mismatch@example.com", "password": "WrongPassword1!"},
                format="json",
            )

        assert response.status_code == 401
        assert response.data["code"] == "invalid_credentials"
        assert any(record.message == "password_mismatch" for record in caplog.records)
        assert not any(record.message == "identity_authentication_failed" for record in caplog.records)

    def test_login_endpoint_logs_login_rate_limit_checked_event(self, caplog):
        DjangoUser.objects.create_user(
            email="planner-throttle@example.com",
            password="StrongPass1!",
            first_name="Planner",
            last_name="Throttle",
            role="planner",
            is_active=True,
            is_verified=True,
        )

        with caplog.at_level(logging.INFO):
            response = self.client.post(
                reverse("login"),
                {"email": "planner-throttle@example.com", "password": "StrongPass1!"},
                format="json",
            )

        assert response.status_code == 200
        checked_events = [record for record in caplog.records if record.message == "login_rate_limit_checked"]
        assert len(checked_events) >= 1
        assert not any(record.message == "password_recovery_rate_limit_checked" for record in caplog.records)
