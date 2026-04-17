from django.contrib.auth.signals import user_logged_in, user_logged_out, user_login_failed
from django.dispatch import receiver

from infrastructure.events.event_bus import EventBus

from domain.events.user_events import (
    UserLoggedIn,
    SessionRevoked,
)


bus = EventBus.get_instance()


# -----------------------------
# LOGIN SUCCESS
# -----------------------------

@receiver(user_logged_in)
def on_user_logged_in(sender, request, user, **kwargs):
    """
    Fired when Django authentication succeeds.

    NOTE:
    - No security logic here
    - Only event publishing
    """

    ip_address = get_client_ip(request)

    bus.publish(
        UserLoggedIn(
            user_id=str(user.id),
            ip_address=ip_address,
        )
    )


# -----------------------------
# LOGOUT EVENT
# -----------------------------

@receiver(user_logged_out)
def on_user_logged_out(sender, request, user, **kwargs):
    """
    Fired when user logs out.
    """

    if not user:
        return

    bus.publish(
        SessionRevoked(
            session_id=str(get_session_id(request)),
        )
    )


# -----------------------------
# LOGIN FAILED (optional security signal)
# -----------------------------

@receiver(user_login_failed)
def on_login_failed(sender, credentials, request, **kwargs):
    """
    IMPORTANT:
    - DO NOT authenticate here
    - Only emit security observation if needed
    """

    # You could later publish:
    # SuspiciousLoginDetected event via RiskEngine

    pass


# -----------------------------
# HELPERS (pure utility only)
# -----------------------------

def get_client_ip(request):
    """
    Extract client IP safely.
    No business logic.
    """
    x_forwarded = request.META.get("HTTP_X_FORWARDED_FOR")
    if x_forwarded:
        return x_forwarded.split(",")[0]
    return request.META.get("REMOTE_ADDR")


def get_session_id(request):
    """
    Extract session ID safely.
    """
    return request.session.session_key