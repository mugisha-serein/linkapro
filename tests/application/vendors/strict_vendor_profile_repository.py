from __future__ import annotations

from typing import Any, Callable
import uuid

from domain.vendors.profile.entity import VendorProfile, VendorStatus
from domain.vendors.profile.interfaces import IVendorProfileRepository
from domain.vendors.shared.pagination import Page, PageRequest


class StrictVendorProfileRepository(IVendorProfileRepository):
    """Strict adapter around a focused test double.

    The adapter explicitly exposes the complete vendor-profile repository port.
    A test's focused delegate must implement every operation that the use case is
    expected to call; any other repository operation fails immediately.
    """

    def __init__(self, delegate: object) -> None:
        object.__setattr__(self, "_delegate", delegate)
        object.__setattr__(self, "contract_calls", [])

    def add(self, profile: VendorProfile) -> VendorProfile:
        return self._invoke("add", profile)

    def get_by_id(self, vendor_id: uuid.UUID) -> VendorProfile | None:
        return self._invoke("get_by_id", vendor_id)

    def get_by_user_id(self, user_id: uuid.UUID) -> VendorProfile | None:
        return self._invoke("get_by_user_id", user_id)

    def list_by_status(
        self,
        status: VendorStatus,
        page: PageRequest | None = None,
    ) -> Page[VendorProfile]:
        return self._invoke("list_by_status", status, page)

    def save(
        self,
        profile: VendorProfile,
        *,
        expected_version: int,
    ) -> VendorProfile:
        return self._invoke(
            "save",
            profile,
            expected_version=expected_version,
        )

    def delete(self, vendor_id: uuid.UUID) -> None:
        self._invoke("delete", vendor_id)

    def _invoke(self, method_name: str, *args: object, **kwargs: object) -> Any:
        delegate_method = getattr(self._delegate, method_name, None)
        if not callable(delegate_method):
            raise AssertionError(
                f"Unexpected IVendorProfileRepository call: {method_name}"
            )
        self.contract_calls.append((method_name, args, kwargs))
        return delegate_method(*args, **kwargs)

    def __getattr__(self, name: str) -> Any:
        try:
            return getattr(self._delegate, name)
        except AttributeError as exc:
            raise AssertionError(
                f"Unexpected vendor-profile repository fake access: {name}"
            ) from exc

    def __setattr__(self, name: str, value: object) -> None:
        if name in {"_delegate", "contract_calls"}:
            object.__setattr__(self, name, value)
            return
        setattr(self._delegate, name, value)


def strict_vendor_profile_repository_factory(
    delegate_type: type,
) -> Callable[..., StrictVendorProfileRepository]:
    def create(*args: object, **kwargs: object) -> StrictVendorProfileRepository:
        return StrictVendorProfileRepository(delegate_type(*args, **kwargs))

    create.__name__ = delegate_type.__name__
    create.__qualname__ = delegate_type.__qualname__
    return create
