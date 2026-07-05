import logging

from django.dispatch import receiver

from django_app.identity.session_revocation import revoke_user_sessions
from infrastructure.adapters.django_event_dispatcher import user_password_changed

logger = logging.getLogger(__name__)


@receiver(user_password_changed)
def revoke_sessions_after_password_change(sender, event, **kwargs):
    user_id = getattr(event, "user_id", None)
    if not user_id:
        logger.warning("identity_password_change_event_missing_user_id")
        return
    revoke_user_sessions(user_id, reason="password_change")
