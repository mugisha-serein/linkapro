from django.db.models.signals import post_save
from django.dispatch import receiver

from django_app.events.models import Event
from django_app.events.template_seeders_init import ensure_rwanda_wedding_template
from django_app.events.workspace_service import generate_event_workspace


@receiver(post_save, sender=Event)
def create_wedding_workspace_on_event_create(sender, instance: Event, created: bool, **kwargs):
    if not created:
        return
    if instance.event_type != Event.EventType.WEDDING:
        return
    if (instance.country or "Rwanda").lower() != "rwanda":
        return
    ensure_rwanda_wedding_template()
    generate_event_workspace(instance)
