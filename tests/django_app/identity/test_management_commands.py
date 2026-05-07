from io import StringIO

import pytest
from django.core.management import call_command

from django_app.identity.models import User


pytestmark = pytest.mark.django_db


class TestRepairDoubleHashedPasswordsCommand:
    def test_dry_run_lists_matching_users_without_changing_password(self):
        user = User.objects.create_user(
            email="repair@example.com",
            password="StrongPass1",
            first_name="Repair",
            last_name="Target",
            role="planner",
        )
        original_password_hash = user.password

        stdout = StringIO()
        call_command(
            "repair_double_hashed_passwords",
            "--email",
            "repair@example.com",
            stdout=stdout,
        )

        user.refresh_from_db()
        output = stdout.getvalue()
        assert "Found 1 candidate user(s)." in output
        assert "DRY RUN repair@example.com" in output
        assert user.password == original_password_hash

    def test_apply_assigns_new_temporary_password(self):
        user = User.objects.create_user(
            email="apply@example.com",
            password="StrongPass1",
            first_name="Apply",
            last_name="Target",
            role="planner",
        )
        original_password_hash = user.password

        stdout = StringIO()
        call_command(
            "repair_double_hashed_passwords",
            "--email",
            "apply@example.com",
            "--apply",
            stdout=stdout,
        )

        user.refresh_from_db()
        output = stdout.getvalue()
        assert "apply@example.com temporary_password=" in output
        assert user.password != original_password_hash

        temporary_password = output.strip().split("temporary_password=")[1]
        assert user.check_password(temporary_password) is True
