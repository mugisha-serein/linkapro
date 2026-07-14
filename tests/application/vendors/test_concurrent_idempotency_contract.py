from __future__ import annotations

from concurrent.futures import ThreadPoolExecutor
from dataclasses import dataclass
from threading import Event, Lock
import uuid

from application.vendors.profile.commands import CreateVendorProfileCommand
from application.vendors.shared.commands import AuthenticatedActor
from application.vendors.shared.handlers import VendorCommandHandlers


@dataclass
class _IdempotencyRecord:
    payload_fingerprint: str
    completed: Event
    result: object | None = None
    error: BaseException | None = None


class StrictUnusedDependency:
    def _unexpected(self, name):
        raise AssertionError(f"Unexpected dependency access: {name}")

    def get_by_id(self, *args, **kwargs): self._unexpected("get_by_id")
    def get_by_user_id(self, *args, **kwargs): self._unexpected("get_by_user_id")
    def get_for_vendor(self, *args, **kwargs): self._unexpected("get_for_vendor")
    def add_with_pending_events(self, *args, **kwargs): self._unexpected("add_with_pending_events")
    def save_with_pending_events(self, *args, **kwargs): self._unexpected("save_with_pending_events")
    def assert_actor_owns_vendor(self, *args, **kwargs): self._unexpected("assert_actor_owns_vendor")
    def assert_actor_can_access_vendor(self, *args, **kwargs): self._unexpected("assert_actor_can_access_vendor")
    def assert_moderator_can_moderate_vendor(self, *args, **kwargs): self._unexpected("assert_moderator_can_moderate_vendor")
    def execute_once(self, *args, **kwargs): self._unexpected("execute_once")
    def assert_inquiry_allowed(self, *args, **kwargs): self._unexpected("assert_inquiry_allowed")
    def load_active_vendor_images(self, *args, **kwargs): self._unexpected("load_active_vendor_images")
    def persist_reorder(self, *args, **kwargs): self._unexpected("persist_reorder")
    def create_at_next_order(self, *args, **kwargs): self._unexpected("create_at_next_order")


class StrictConcurrentIdempotencyPort:
    """Test fake that serializes one operation per idempotency identity."""

    def __init__(self) -> None:
        self._lock = Lock()
        self._records: dict[tuple[str, uuid.UUID, str], _IdempotencyRecord] = {}
        self.operation_claims = 0

    def execute_once(
        self,
        *,
        scope: str,
        actor_id: uuid.UUID,
        key: str,
        payload_fingerprint: str,
        operation,
    ):
        record_key = (scope, actor_id, key)

        with self._lock:
            record = self._records.get(record_key)
            if record is None:
                record = _IdempotencyRecord(
                    payload_fingerprint=payload_fingerprint,
                    completed=Event(),
                )
                self._records[record_key] = record
                self.operation_claims += 1
                owns_operation = True
            else:
                assert record.payload_fingerprint == payload_fingerprint
                owns_operation = False

        if owns_operation:
            try:
                result = operation()
            except BaseException as exc:
                with self._lock:
                    record.error = exc
                    record.completed.set()
                raise

            with self._lock:
                record.result = result
                record.completed.set()
            return result

        assert record.completed.wait(timeout=2), "The first idempotent call did not complete."
        if record.error is not None:
            raise record.error
        return record.result


def _handler(idempotency_port: StrictConcurrentIdempotencyPort) -> VendorCommandHandlers:
    unused = StrictUnusedDependency()
    return VendorCommandHandlers(
        vendor_repo=unused,
        image_repo=unused,
        package_repo=unused,
        inquiry_repo=unused,
        aggregate_uow=unused,
        authorization_port=unused,
        inquiry_abuse_protection_port=unused,
        portfolio_creation_port=unused,
        reorder_uow=unused,
        idempotency_port=idempotency_port,
    )


def test_concurrent_identical_idempotent_calls_execute_once_and_replay_completed_result():
    actor = AuthenticatedActor(user_id=uuid.uuid4())
    command = CreateVendorProfileCommand(
        actor=actor,
        business_name="Concurrent Vendor",
        category="catering",
        description="Reliable vendor services for complete event support.",
        service_area="Kigali",
        contact_email="vendor@example.com",
        contact_phone="+250700000000",
        idempotency_key="same-key",
    )
    idempotency_port = StrictConcurrentIdempotencyPort()
    handler = _handler(idempotency_port)
    operation_started = Event()
    allow_completion = Event()
    execution_count = 0
    execution_lock = Lock()
    completed_result = object()

    def operation():
        nonlocal execution_count
        with execution_lock:
            execution_count += 1
        operation_started.set()
        assert allow_completion.wait(timeout=2), "The test did not release the operation."
        return completed_result

    def invoke():
        return handler._run_required_idempotent(
            "vendor_profile.create",
            actor.user_id,
            command.idempotency_key,
            command,
            operation,
        )

    with ThreadPoolExecutor(max_workers=2) as executor:
        first = executor.submit(invoke)
        assert operation_started.wait(timeout=2), "The first operation did not start."
        second = executor.submit(invoke)
        allow_completion.set()
        first_result = first.result(timeout=2)
        second_result = second.result(timeout=2)

    assert execution_count == 1
    assert idempotency_port.operation_claims == 1
    assert first_result is completed_result
    assert second_result is completed_result
    assert first_result is second_result
