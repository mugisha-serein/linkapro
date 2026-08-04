from __future__ import annotations

from types import SimpleNamespace
import uuid

import pytest

from application.vendors.errors import VendorConflict, VendorIdempotencyConflict
from infrastructure.adapters import django_vendor_idempotency as idempotency_module
from infrastructure.adapters.django_vendor_idempotency import DjangoVendorIdempotencyAdapter


class FakeManager:
    def __init__(self, record):
        self.record = record

    def select_for_update(self):
        return self

    def get_or_create(self, **kwargs):
        return self.record, False


class FakeRecordModel:
    class Status:
        COMPLETED = "completed"
        IN_PROGRESS = "in_progress"
        FAILED = "failed"


def test_payload_mismatch_raises_dedicated_idempotency_conflict(monkeypatch):
    record = SimpleNamespace(
        payload_fingerprint="original-fingerprint",
        status=FakeRecordModel.Status.COMPLETED,
    )
    FakeRecordModel.objects = FakeManager(record)
    monkeypatch.setattr(idempotency_module, "VendorIdempotencyRecord", FakeRecordModel)

    with pytest.raises(VendorIdempotencyConflict) as exc_info:
        DjangoVendorIdempotencyAdapter()._reserve(
            scope="vendor_profile.create",
            actor_id=uuid.uuid4(),
            key="same-key",
            fingerprint="different-fingerprint",
        )

    assert exc_info.value.code == "vendor_idempotency_conflict"


def test_in_progress_reuse_remains_an_ordinary_vendor_conflict(monkeypatch):
    record = SimpleNamespace(
        payload_fingerprint="same-fingerprint",
        status=FakeRecordModel.Status.IN_PROGRESS,
    )
    adapter = DjangoVendorIdempotencyAdapter()
    monkeypatch.setattr(idempotency_module, "VendorIdempotencyRecord", FakeRecordModel)
    monkeypatch.setattr(adapter, "_reserve", lambda *args: (record, False))

    class AtomicContext:
        def __enter__(self):
            return None

        def __exit__(self, exc_type, exc, traceback):
            return False

    monkeypatch.setattr(idempotency_module.transaction, "atomic", AtomicContext)

    with pytest.raises(VendorConflict) as exc_info:
        adapter.execute_once(
            scope="vendor_profile.create",
            actor_id=uuid.uuid4(),
            key="same-key",
            payload_fingerprint="same-fingerprint",
            operation=lambda: object(),
        )

    error = exc_info.value
    assert type(error) is VendorConflict
    assert not isinstance(error, VendorIdempotencyConflict)
    assert error.code == "vendor_idempotency_in_progress"
