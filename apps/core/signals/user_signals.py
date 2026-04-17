from django.db.models.signals import post_save, pre_delete
from django.dispatch import receiver

from infrastructure.persistence.models.user_model import UserModel as User  

from infrastructure.events.event_bus import EventBus
from domain.events.user_events import (
    UserRegistered,
    UserLoggedIn,
)


bus = EventBus.get_instance()


# -----------------------------
# USER CREATED SIGNAL
# -----------------------------

@receiver(post_save, sender=User)
def user_created_signal(sender, instance, created, **kwargs):
    """
    Triggered when a new user is created in DB.

    IMPORTANT:
    - No business logic here
    - Only publish domain event
    """

    if created:
        event = UserRegistered(
            user_id=str(instance.id),
            email=instance.email,
        )

        bus.publish(event)


# -----------------------------
# USER LOGIN SIGNAL (OPTIONAL PATTERN)
# -----------------------------
# Django does NOT provide login signal by default in model layer.
# You usually call this manually from LoginHandler.

def emit_user_logged_in(user, ip_address: str):
    """
    Manual signal-style helper (recommended for auth systems).
    """

    event = UserLoggedIn(
        user_id=str(user.id),
        ip_address=ip_address,
    )

    bus.publish(event)


# -----------------------------
# USER DELETE SIGNAL (optional extension)
# -----------------------------

@receiver(pre_delete, sender=User)
def user_deleted_signal(sender, instance, **kwargs):
    """
    Optional: emit audit events before deletion.
    """

    # You can define a UserDeleted event if needed
    pass