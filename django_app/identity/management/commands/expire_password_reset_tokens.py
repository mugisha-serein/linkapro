from django.core.management.base import BaseCommand
from django.utils import timezone

from django_app.identity.models import PasswordResetToken


class Command(BaseCommand):
    help = "Mark expired active password reset tokens as expired."

    def handle(self, *args, **options):
        now = timezone.now()
        expired_count = PasswordResetToken.objects.filter(
            status=PasswordResetToken.Status.ACTIVE,
            expires_at__lte=now,
        ).update(status=PasswordResetToken.Status.EXPIRED, updated_at=now)

        self.stdout.write(self.style.SUCCESS(f"Expired {expired_count} password reset token(s)."))
