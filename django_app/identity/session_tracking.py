from __future__ import annotations

from django.db import IntegrityError
from django.utils import timezone

from application.identity.ports import SESSION_ID_CLAIM

DEFAULT_DEVICE_LABEL = "Unknown device"


def create_identity_session(
    *,
    user_id: str,
    token_family: str,
    device_label: str | None = None,
    user_agent_hash: str | None = None,
    ip_hash: str | None = None,
) -> str:
    from django_app.identity.models import IdentitySession

    label = (device_label or DEFAULT_DEVICE_LABEL).strip() or DEFAULT_DEVICE_LABEL
    now = timezone.now()
    try:
        identity_session = IdentitySession.objects.create(
            user_id=user_id,
            token_family=token_family,
            device_label=label,
            user_agent_hash=user_agent_hash,
            ip_hash=ip_hash,
            created_at=now,
            last_seen_at=now,
        )
    except IntegrityError:
        identity_session = IdentitySession.objects.get(token_family=token_family)
    return str(identity_session.id)


def touch_identity_session(session_id: str | None, token_family: str | None = None) -> None:
    if not session_id:
        return
    from django_app.identity.models import IdentitySession

    filters = {"id": session_id, "revoked_at__isnull": True}
    if token_family:
        filters["token_family"] = token_family
    IdentitySession.objects.filter(**filters).update(last_seen_at=timezone.now())


def identity_session_is_active(session_id: str | None, token_family: str | None = None) -> bool:
    if not session_id:
        return True
    from django_app.identity.models import IdentitySession

    filters = {"id": session_id, "revoked_at__isnull": True}
    if token_family:
        filters["token_family"] = token_family
    return IdentitySession.objects.filter(**filters).exists()


def revoke_identity_session(
    *,
    session_id: str | None = None,
    token_family: str | None = None,
    reason: str = "session_revoked",
) -> None:
    if not session_id and not token_family:
        return
    from django_app.identity.models import IdentitySession

    filters = {"revoked_at__isnull": True}
    if session_id:
        filters["id"] = session_id
    if token_family:
        filters["token_family"] = token_family
    IdentitySession.objects.filter(**filters).update(
        revoked_at=timezone.now(),
        revoked_reason=reason[:255],
    )
