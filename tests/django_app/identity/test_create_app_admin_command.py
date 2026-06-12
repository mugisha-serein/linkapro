import pytest
from django.core.management import call_command

from django_app.identity.models import User

pytestmark = pytest.mark.django_db


def test_create_app_admin_command_creates_staff_app_admin(monkeypatch):
    monkeypatch.setenv("LINKAPRO_ADMIN_PASSWORD", "Str0ng-admin-pass-123")

    call_command(
        "create_app_admin",
        "--email",
        "admin@example.com",
        "--first-name",
        "Admin",
        "--last-name",
        "User",
        "--password-env",
        "LINKAPRO_ADMIN_PASSWORD",
    )

    user = User.objects.get(email="admin@example.com")
    assert user.role == "admin"
    assert user.is_staff is True
    assert user.is_superuser is False
    assert user.check_password("Str0ng-admin-pass-123")


def test_create_app_admin_requires_explicit_promote_existing(monkeypatch):
    monkeypatch.setenv("LINKAPRO_ADMIN_PASSWORD", "Str0ng-admin-pass-123")
    User.objects.create_user(
        email="planner@example.com",
        password="old-pass",
        first_name="Plan",
        last_name="Ner",
        role="planner",
    )

    with pytest.raises(Exception):
        call_command(
            "create_app_admin",
            "--email",
            "planner@example.com",
            "--password-env",
            "LINKAPRO_ADMIN_PASSWORD",
        )
