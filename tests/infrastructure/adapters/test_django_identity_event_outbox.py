from dataclasses import dataclass
from datetime import datetime, timezone
import uuid

import pytest

from infrastructure.adapters.django_identity_event_outbox import DjangoIdentityEventOutboxDispatcher


@dataclass(frozen=True)
class _Event:
    user_id: uuid.UUID
    occurred_at: datetime
    event_id: uuid.UUID
    auth_token_version: int | None = None


@dataclass(frozen=True)
class _UnsafeEvent:
    user_id: uuid.UUID
    occurred_at: datetime
    event_id: uuid.UUID
    reset_token: str


@dataclass(frozen=True)
class _NestedUnsafeEvent:
    user_id: uuid.UUID
    occurred_at: datetime
    event_id: uuid.UUID
    metadata: dict


def test_identity_event_payload_rejects_secret_shaped_keys():
    event = _UnsafeEvent(
        user_id=uuid.uuid4(),
        occurred_at=datetime.now(timezone.utc),
        event_id=uuid.uuid4(),
        reset_token="raw-token",
    )

    with pytest.raises(ValueError, match="reset_token"):
        DjangoIdentityEventOutboxDispatcher._event_payload(event)


def test_identity_event_payload_rejects_nested_secret_shaped_keys():
    event = _NestedUnsafeEvent(
        user_id=uuid.uuid4(),
        occurred_at=datetime.now(timezone.utc),
        event_id=uuid.uuid4(),
        metadata={"delivery": {"totp_secret": "raw-secret"}},
    )

    with pytest.raises(ValueError, match="totp_secret"):
        DjangoIdentityEventOutboxDispatcher._event_payload(event)


def test_identity_event_payload_keeps_auth_token_version_out_of_payload():
    event = _Event(
        user_id=uuid.uuid4(),
        occurred_at=datetime.now(timezone.utc),
        event_id=uuid.uuid4(),
        auth_token_version=3,
    )

    payload = DjangoIdentityEventOutboxDispatcher._event_payload(event)

    assert "auth_token_version" not in payload
