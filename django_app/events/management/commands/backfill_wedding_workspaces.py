from django.core.exceptions import ImproperlyConfigured
from django.core.management.base import BaseCommand, CommandError

from django_app.events.models import Event
from django_app.events.template_seeders.rwanda_wedding import ensure_rwanda_wedding_template
from django_app.events.workspace_service import generate_event_workspace


class Command(BaseCommand):
    help = "Generate missing Rwanda wedding workspaces for existing events."

    def handle(self, *args, **options):
        try:
            ensure_rwanda_wedding_template()
        except ImproperlyConfigured as exc:
            raise CommandError(str(exc)) from exc

        generated = 0
        skipped = 0
        failed = 0
        events = Event.objects.filter(event_type=Event.EventType.WEDDING, country__iexact="Rwanda").order_by("created_at")

        for event in events:
            if event.workspace_stages.exists():
                skipped += 1
                continue
            try:
                stages = generate_event_workspace(event)
            except Exception as exc:
                failed += 1
                self.stderr.write(self.style.ERROR(f"Failed {event.id}: {exc}"))
                continue
            if stages:
                generated += 1
            else:
                skipped += 1

        summary = {"generated": generated, "skipped": skipped, "failed": failed}
        self.stdout.write(self.style.SUCCESS(", ".join(f"{key}={value}" for key, value in summary.items())))
        if failed:
            raise CommandError(f"Failed to backfill {failed} wedding workspace(s).")
