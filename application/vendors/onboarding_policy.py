from __future__ import annotations

from dataclasses import dataclass
from enum import StrEnum
from typing import Any

from domain.vendors.profile_completion import (
    REQUIRED_VENDOR_PROFILE_FIELDS,
    get_vendor_profile_completion_errors,
)

from .ports import VendorProfileCompletionProvider


class VendorOnboardingRedirectIntent(StrEnum):
    COMPLETE_PROFILE = "COMPLETE_PROFILE"
    OPEN_DASHBOARD = "OPEN_DASHBOARD"


COMPLETE_PROFILE = VendorOnboardingRedirectIntent.COMPLETE_PROFILE
OPEN_DASHBOARD = VendorOnboardingRedirectIntent.OPEN_DASHBOARD
SETUP_ROUTE = COMPLETE_PROFILE
DASHBOARD_ROUTE = OPEN_DASHBOARD
_SUPPORTED_VENDOR_STATUSES = frozenset(
    {"draft", "pending_review", "approved", "rejected", "suspended"}
)
_PROVIDER_OMITTED = object()


class DomainVendorProfileCompletionProvider:
    """Application adapter for the domain-owned profile completion policy."""

    def get_profile_completion_errors(self, profile: object):
        return get_vendor_profile_completion_errors(profile)


DEFAULT_VENDOR_PROFILE_COMPLETION_PROVIDER = DomainVendorProfileCompletionProvider()


@dataclass(frozen=True)
class VendorOnboardingDTO(dict[str, Any]):
    profile_status: str
    can_access_dashboard: bool
    must_complete_profile: bool
    can_submit_for_review: bool
    marketplace_visible: bool
    redirect_to: VendorOnboardingRedirectIntent
    message: str

    def __post_init__(self) -> None:
        dict.__init__(
            self,
            profile_status=self.profile_status,
            can_access_dashboard=self.can_access_dashboard,
            must_complete_profile=self.must_complete_profile,
            can_submit_for_review=self.can_submit_for_review,
            marketplace_visible=self.marketplace_visible,
            redirect_to=self.redirect_to,
            message=self.message,
        )

    def _reject_mutation(self, *args: Any, **kwargs: Any) -> None:
        raise TypeError("VendorOnboardingDTO is immutable.")

    __setitem__ = _reject_mutation
    __delitem__ = _reject_mutation
    __ior__ = _reject_mutation
    clear = _reject_mutation
    pop = _reject_mutation
    popitem = _reject_mutation
    setdefault = _reject_mutation
    update = _reject_mutation


def build_vendor_onboarding_contract(
    profile: Any | None,
    completion_provider: VendorProfileCompletionProvider | object = _PROVIDER_OMITTED,
) -> VendorOnboardingDTO:
    if profile is None:
        return VendorOnboardingDTO(
            profile_status="missing",
            can_access_dashboard=False,
            must_complete_profile=True,
            can_submit_for_review=False,
            marketplace_visible=False,
            redirect_to=COMPLETE_PROFILE,
            message="Complete your vendor profile before continuing.",
        )

    status = _normalize_vendor_status(profile)
    field_errors = vendor_field_errors(profile, completion_provider)
    is_complete = not field_errors

    if status == "approved":
        return VendorOnboardingDTO(
            profile_status=status,
            can_access_dashboard=True,
            must_complete_profile=False,
            can_submit_for_review=False,
            marketplace_visible=True,
            redirect_to=OPEN_DASHBOARD,
            message="Your vendor profile is approved and visible in the marketplace.",
        )

    if status == "pending_review":
        return VendorOnboardingDTO(
            profile_status=status,
            can_access_dashboard=True,
            must_complete_profile=False,
            can_submit_for_review=False,
            marketplace_visible=False,
            redirect_to=OPEN_DASHBOARD,
            message="Your profile is under review. Marketplace visibility starts after admin approval.",
        )

    if status == "suspended":
        return VendorOnboardingDTO(
            profile_status=status,
            can_access_dashboard=False,
            must_complete_profile=False,
            can_submit_for_review=False,
            marketplace_visible=False,
            redirect_to=COMPLETE_PROFILE,
            message="Your vendor account is suspended. Please contact support.",
        )

    if status == "rejected":
        return VendorOnboardingDTO(
            profile_status=status,
            can_access_dashboard=False,
            must_complete_profile=True,
            can_submit_for_review=is_complete,
            marketplace_visible=False,
            redirect_to=COMPLETE_PROFILE,
            message=getattr(profile, "rejection_reason", None)
            or "Your vendor profile needs updates before resubmission.",
        )

    incomplete_status = "incomplete" if not is_complete else status
    return VendorOnboardingDTO(
        profile_status=incomplete_status,
        can_access_dashboard=False,
        must_complete_profile=True,
        can_submit_for_review=is_complete,
        marketplace_visible=False,
        redirect_to=COMPLETE_PROFILE,
        message="Complete your vendor profile before continuing."
        if not is_complete
        else "Submit your vendor profile for admin review.",
    )


def vendor_field_errors(
    profile: Any | None,
    completion_provider: VendorProfileCompletionProvider | object = _PROVIDER_OMITTED,
) -> dict[str, list[str]]:
    if profile is None:
        return {}

    provider = _resolve_completion_provider(profile, completion_provider)
    return {
        field_name: list(messages)
        for field_name, messages in provider.get_profile_completion_errors(profile).items()
    }


def _resolve_completion_provider(
    profile: object,
    completion_provider: VendorProfileCompletionProvider | object,
) -> VendorProfileCompletionProvider:
    if completion_provider is not _PROVIDER_OMITTED:
        return completion_provider  # type: ignore[return-value]

    if all(hasattr(profile, field_name) for field_name in REQUIRED_VENDOR_PROFILE_FIELDS):
        return DEFAULT_VENDOR_PROFILE_COMPLETION_PROVIDER

    raise TypeError("vendor_field_errors() missing 1 required positional argument: 'completion_provider'")


def _normalize_vendor_status(profile: Any) -> str:
    raw_status = getattr(profile, "status", "draft")
    status_value = getattr(raw_status, "value", raw_status)
    normalized_status = str(status_value or "draft").strip().lower()
    if not normalized_status:
        normalized_status = "draft"
    if normalized_status not in _SUPPORTED_VENDOR_STATUSES:
        raise ValueError(f"Unsupported vendor status: {normalized_status}")
    return normalized_status
