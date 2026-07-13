from __future__ import annotations

import pytest

from tests.application.vendors.strict_vendor_profile_repository import (
    StrictVendorProfileRepository,
    strict_vendor_profile_repository_factory,
)


@pytest.fixture(autouse=True)
def replace_vendor_profile_repository_test_fake(monkeypatch, request):
    """Wrap only local vendor-profile repository doubles in the strict port fake."""

    test_module = request.module
    for fake_name in ("VendorRepo", "VendorRepository"):
        delegate_type = getattr(test_module, fake_name, None)
        if not isinstance(delegate_type, type):
            continue
        if delegate_type is StrictVendorProfileRepository:
            continue
        if delegate_type.__module__ != test_module.__name__:
            continue
        monkeypatch.setattr(
            test_module,
            fake_name,
            strict_vendor_profile_repository_factory(delegate_type),
        )
