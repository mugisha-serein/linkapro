from django.core.exceptions import ImproperlyConfigured
from django.core.management.base import BaseCommand, CommandError

from django_app.events.template_seeders.rwanda_wedding import seed_rwanda_wedding_template


class Command(BaseCommand):
    help = "Create or refresh the active Rwanda wedding workspace template."

    def handle(self, *args, **options):
        try:
            result = seed_rwanda_wedding_template()
        except ImproperlyConfigured as exc:
            raise CommandError(str(exc)) from exc

        summary = ", ".join(f"{key}={value}" for key, value in result["totals"].items())
        self.stdout.write(self.style.SUCCESS(f"Seeded {result['template'].slug}: {summary}"))
