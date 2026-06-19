from django.conf import settings
from django.core.mail import send_mail
from django.core.management.base import BaseCommand, CommandError


class Command(BaseCommand):
    help = "Send a test email using the configured Django email backend."

    def add_arguments(self, parser):
        parser.add_argument("--to", required=True, help="Recipient email address.")

    def handle(self, *args, **options):
        recipient = options["to"].strip()
        if not recipient:
            raise CommandError("--to is required.")

        try:
            sent_count = send_mail(
                subject="LinkaPro email configuration test",
                message="This is a LinkaPro test email sent with the configured Django email backend.",
                from_email=settings.DEFAULT_FROM_EMAIL,
                recipient_list=[recipient],
                fail_silently=False,
            )
        except Exception as exc:
            raise CommandError(f"Test email failed: {exc.__class__.__name__}: {exc}") from exc

        if sent_count != 1:
            raise CommandError("Test email was not sent.")

        self.stdout.write(self.style.SUCCESS(f"Test email sent to {recipient} using {settings.EMAIL_BACKEND}"))
