from __future__ import annotations

from dataclasses import dataclass
from enum import StrEnum
from typing import Any

from domain.vendors.entities import VendorProfile
from domain.vendors.entities import profile_completion_errors_for


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
CREATE_VENDOR_PROFILE_ACTION = {
    "method": "POST",
    "path": "/api/django/vendors/profile/",
}


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
    action: dict[str, str] | None
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
            action=self.action,
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
            redirect_to=SETUP_ROUTE,
            action=dict(CREATE_VENDOR_PROFILE_ACTION),
            message="Complete your vendor profile before continuing.",
        )

    status = str(getattr(profile, "status", "draft") or "draft")
    field_errors = vendor_field_errors(profile)
    is_complete = not field_errors

    if status == "approved":
        return VendorOnboardingDTO(
            profile_status=status,
            can_access_dashboard=True,
            must_complete_profile=False,
            can_submit_for_review=False,
            marketplace_visible=True,
            redirect_to=OPEN_DASHBOARD,
            action=None,
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
            action=None,
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
            action=None,
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
            action=None,
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
        action=dict(CREATE_VENDOR_PROFILE_ACTION) if not is_complete else None,
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
    if hasattr(profile, "get_profile_completion_errors"):
        return profile.get_profile_completion_errors()
    return profile_completion_errors_for(profile, VendorProfile.required_profile_fields())
