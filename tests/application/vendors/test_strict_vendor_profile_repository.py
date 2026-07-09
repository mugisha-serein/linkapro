from __future__ import annotations

import inspect
import uuid

import pytest

from domain.vendors.entities import VendorProfile, VendorStatus
from domain.vendors.interfaces import IVendorProfileRepository, PageRequest
from tests.application.vendors.strict_vendor_profile_repository import (
    StrictVendorProfileRepository,
)


class FocusedGetByIdDelegate:
    def __init__(self, profile: VendorProfile | None = None) -> None:
        self.profile = profile
        self.calls: list[uuid.UUID] = []

    def get_by_id(self, vendor_id: uuid.UUID) -> VendorProfile | None:
        self.calls.append(vendor_id)
        if self.profile is None or self.profile.id != vendor_id:
            return None
        return self.profile


def test_strict_vendor_profile_repository_explicitly_implements_complete_port():
    assert StrictVendorProfileRepository.__abstractmethods__ == frozenset()
    assert issubclass(StrictVendorProfileRepository, IVendorProfileRepository)
    assert {
        "add",
        "get_by_id",
        "get_by_user_id",
        "list_by_status",
        "save",
        "delete",
    }.issubset(StrictVendorProfileRepository.__dict__)

    assert inspect.signature(StrictVendorProfileRepository.add).parameters.keys() == {
        "self",
        "profile",
    }
    assert inspect.signature(
        StrictVendorProfileRepository.list_by_status
    ).parameters.keys() == {"self", "status", "page"}
    assert inspect.signature(StrictVendorProfileRepository.save).parameters[
        "expected_version"
    ].kind is inspect.Parameter.KEYWORD_ONLY


def test_strict_vendor_profile_repository_delegates_expected_calls_and_records_them():
    vendor_id = uuid.uuid4()
    delegate = FocusedGetByIdDelegate()
    repository = StrictVendorProfileRepository(delegate)

    assert repository.get_by_id(vendor_id) is None
    assert delegate.calls == [vendor_id]
    assert repository.contract_calls == [
        ("get_by_id", (vendor_id,), {}),
    ]


def test_strict_vendor_profile_repository_raises_for_every_unexpected_contract_call():
    repository = StrictVendorProfileRepository(FocusedGetByIdDelegate())
    profile = object()

    unexpected_calls = (
        lambda: repository.add(profile),
        lambda: repository.get_by_user_id(uuid.uuid4()),
        lambda: repository.list_by_status(
            VendorStatus.DRAFT,
            PageRequest(limit=10, offset=0),
        ),
        lambda: repository.save(profile, expected_version=0),
        lambda: repository.delete(uuid.uuid4()),
    )

    for call in unexpected_calls:
        with pytest.raises(
            AssertionError,
            match="Unexpected IVendorProfileRepository call",
        ):
            call()


def test_strict_vendor_profile_repository_rejects_non_contract_fake_access():
    repository = StrictVendorProfileRepository(FocusedGetByIdDelegate())

    with pytest.raises(
        AssertionError,
        match="Unexpected vendor-profile repository fake access",
    ):
        repository.unplanned_helper()
