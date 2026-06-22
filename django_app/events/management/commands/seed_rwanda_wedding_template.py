from django.core.management.base import BaseCommand

from django_app.events.template_seeders_init import seed_rwanda_wedding_template


class Command(BaseCommand):
    help = "Create or refresh the active Rwanda wedding workspace template."

    def handle(self, *args, **options):
        totals = seed_rwanda_wedding_template()
        summary = ", ".join(f"{key}={value}" for key, value in totals.items())
        self.stdout.write(self.style.SUCCESS(f"Seeded Rwanda wedding template: {summary}"))
