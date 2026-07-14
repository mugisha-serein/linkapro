from __future__ import annotations

import inspect
import uuid

import pytest

from application.vendors.profile.commands import SubmitVendorForReviewCommand, UpdateVendorProfileCommand
from application.vendors.shared.commands import AuthenticatedActor
from application.vendors.errors import InvalidVendorCommand
from application.vendors.profile.handlers import _translate_profile_update_validation
from application.vendors.shared.handlers import VendorCommandHandlers
from domain.vendors.profile.errors import InvalidVendorTransition, VendorProfileValidationError


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


class AuthorizationPort:
    def assert_actor_owns_vendor(self, actor, vendor_id):
        return None


class AggregateUnitOfWork:
    def __init__(self):
        self.save_calls = []

    def save_with_pending_events(self, aggregate, *, expected_version):
        self.save_calls.append((aggregate, expected_version))
        return aggregate


class VendorRepository:
    def __init__(self, profile=None, error=None):
        self.profile = profile
        self.error = error

    def get_by_id(self, vendor_id):
        if self.error is not None:
            raise self.error
        return self.profile


class ValidationFailingProfile:
    def __init__(self, field_errors):
        self.id = uuid.uuid4()
        self.version = 2
        self.field_errors = field_errors
        self.received_updates = None

    def update_details(self, **updates):
        self.received_updates = updates
        raise VendorProfileValidationError(field_errors=self.field_errors)


class TransitionFailingProfile:
    def __init__(self):
        self.id = uuid.uuid4()
        self.version = 1

    def submit_for_review(self):
        raise InvalidVendorTransition("Cannot submit from current status.")


def _handler(vendor_repo, aggregate_uow=None):
    unused = StrictUnusedDependency()
    return VendorCommandHandlers(
        vendor_repo=vendor_repo,
        image_repo=unused,
        package_repo=unused,
        inquiry_repo=unused,
        idempotency_port=unused,
        inquiry_abuse_protection_port=unused,
        portfolio_creation_port=unused,
        reorder_uow=unused,
        aggregate_uow=aggregate_uow or AggregateUnitOfWork(),
        authorization_port=AuthorizationPort(),
    )


def test_private_translation_helper_preserves_domain_field_errors():
    field_errors = {
        "contact_email": ["Must be a valid email address."],
        "description": ["Use at least 20 characters for your description."],
    }
    domain_error = VendorProfileValidationError(field_errors=field_errors)

    def operation():
        raise domain_error

    with pytest.raises(InvalidVendorCommand) as exc_info:
        _translate_profile_update_validation(operation)

    error = exc_info.value
    assert error.code == "vendor_command_invalid"
    assert error.message == "Vendor command is invalid."
    assert error.field_errors == field_errors
    assert error.errors == field_errors
    assert error.__cause__ is domain_error


def test_update_profile_translates_domain_validation_to_invalid_command():
    field_errors = {"contact_email": ["Must be a valid email address."]}
    profile = ValidationFailingProfile(field_errors)
    aggregate_uow = AggregateUnitOfWork()
    handler = _handler(VendorRepository(profile=profile), aggregate_uow)
    actor = AuthenticatedActor(user_id=uuid.uuid4())

    with pytest.raises(InvalidVendorCommand) as exc_info:
        handler.update_profile(
            UpdateVendorProfileCommand(
                actor=actor,
                vendor_id=profile.id,
                expected_version=2,
                contact_email="not-an-email",
            )
        )

    assert exc_info.value.field_errors == field_errors
    assert isinstance(exc_info.value.__cause__, VendorProfileValidationError)
    assert profile.received_updates == {"contact_email": "not-an-email"}
    assert aggregate_uow.save_calls == []


def test_update_profile_does_not_translate_repository_errors():
    repository_error = RuntimeError("repository unavailable")
    handler = _handler(VendorRepository(error=repository_error))

    with pytest.raises(RuntimeError) as exc_info:
        handler.update_profile(
            UpdateVendorProfileCommand(
                actor=AuthenticatedActor(user_id=uuid.uuid4()),
                vendor_id=uuid.uuid4(),
                expected_version=0,
                business_name="Updated Vendor",
            )
        )

    assert exc_info.value is repository_error


def test_other_handlers_do_not_translate_transition_errors():
    profile = TransitionFailingProfile()
    handler = _handler(VendorRepository(profile=profile))

    with pytest.raises(InvalidVendorTransition) as exc_info:
        handler.submit_for_review(
            SubmitVendorForReviewCommand(
                actor=AuthenticatedActor(user_id=uuid.uuid4()),
                vendor_id=profile.id,
                expected_version=1,
            )
        )

    assert type(exc_info.value) is InvalidVendorTransition


def test_translation_helper_is_applied_only_to_update_profile():
    module_source = inspect.getsource(inspect.getmodule(VendorCommandHandlers))
    update_source = inspect.getsource(VendorCommandHandlers.update_profile)

    assert module_source.count("_translate_profile_update_validation(") == 2
    assert "_translate_profile_update_validation(" in update_source
