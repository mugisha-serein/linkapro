from io import StringIO
from datetime import timedelta

import pytest
from django.core import mail
from django.core.management import call_command
from django.test import override_settings
from django.utils import timezone

from django_app.identity.models import PasswordResetToken, User


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


class TestSendTestEmailCommand:
    @override_settings(
        EMAIL_BACKEND="django.core.mail.backends.locmem.EmailBackend",
        DEFAULT_FROM_EMAIL="no-reply@example.test",
    )
    def test_send_test_email_uses_configured_backend(self):
        mail.outbox = []
        stdout = StringIO()

        call_command("send_test_email", "--to", "ops@example.com", stdout=stdout)

        assert len(mail.outbox) == 1
        assert mail.outbox[0].subject == "LinkaPro email configuration test"
        assert mail.outbox[0].from_email == "no-reply@example.test"
        assert mail.outbox[0].to == ["ops@example.com"]
        assert "Test email sent to ops@example.com" in stdout.getvalue()


class TestExpirePasswordResetTokensCommand:
    def test_marks_expired_active_tokens(self):
        user = User.objects.create_user(
            email="expire-reset@example.com",
            password="StrongPass1",
            first_name="Expire",
            last_name="Reset",
            role="planner",
        )
        expired = PasswordResetToken.objects.create(
            user=user,
            jti="11111111-1111-1111-1111-111111111111",
            token_hash="a" * 64,
            expires_at=timezone.now() - timedelta(minutes=1),
        )
        current = PasswordResetToken.objects.create(
            user=user,
            jti="22222222-2222-2222-2222-222222222222",
            token_hash="b" * 64,
            expires_at=timezone.now() + timedelta(minutes=10),
        )
        stdout = StringIO()

        call_command("expire_password_reset_tokens", stdout=stdout)

        expired.refresh_from_db()
        current.refresh_from_db()
        assert expired.status == PasswordResetToken.Status.EXPIRED
        assert current.status == PasswordResetToken.Status.ACTIVE
        assert "Expired 1 password reset token(s)." in stdout.getvalue()
