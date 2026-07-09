from __future__ import annotations

from dataclasses import FrozenInstanceError, fields, is_dataclass
from typing import get_type_hints

import pytest

from application.vendors.onboarding_policy import (
    DASHBOARD_ROUTE,
    SETUP_ROUTE,
    VendorOnboardingDTO,
    build_vendor_onboarding_contract,
)


class Profile:
    def __init__(
        self,
        *,
        status="draft",
        field_errors=None,
        rejection_reason=None,
    ):
        self.status = status
        self.rejection_reason = rejection_reason
        self._field_errors = field_errors or {}

    def get_profile_completion_errors(self):
        return self._field_errors


class StringStatus:
    value = "not-used"

    def __str__(self) -> str:
        return "approved"


def test_vendor_onboarding_dto_is_frozen_and_has_exact_typed_fields():
    assert is_dataclass(VendorOnboardingDTO)
    assert tuple(field.name for field in fields(VendorOnboardingDTO)) == (
        "profile_status",
        "can_access_dashboard",
        "must_complete_profile",
        "can_submit_for_review",
        "marketplace_visible",
        "redirect_to",
        "message",
    )
    assert get_type_hints(VendorOnboardingDTO) == {
        "profile_status": str,
        "can_access_dashboard": bool,
        "must_complete_profile": bool,
        "can_submit_for_review": bool,
        "marketplace_visible": bool,
        "redirect_to": str,
        "message": str,
    }

    dto = build_vendor_onboarding_contract(None)
    with pytest.raises(FrozenInstanceError):
        dto.message = "Changed"


@pytest.mark.parametrize(
    "mutation",
    [
        lambda dto: dto.__setitem__("message", "Changed"),
        lambda dto: dto.__delitem__("message"),
        lambda dto: dto.update({"message": "Changed"}),
        lambda dto: dto.setdefault("extra", True),
        lambda dto: dto.pop("message"),
        lambda dto: dto.popitem(),
        lambda dto: dto.clear(),
        lambda dto: dto.__ior__({"extra": True}),
    ],
)
def test_vendor_onboarding_dto_rejects_dictionary_mutation(mutation):
    dto = build_vendor_onboarding_contract(None)

    with pytest.raises(TypeError, match="VendorOnboardingDTO is immutable"):
        mutation(dto)


def test_missing_profile_preserves_exact_contract_and_dictionary_behavior():
    result = build_vendor_onboarding_contract(None)
    expected = {
        "profile_status": "missing",
        "can_access_dashboard": False,
        "must_complete_profile": True,
        "can_submit_for_review": False,
        "marketplace_visible": False,
        "redirect_to": SETUP_ROUTE,
        "message": "Complete your vendor profile before continuing.",
    }

    assert isinstance(result, VendorOnboardingDTO)
    assert isinstance(result, dict)
    assert result == expected
    assert dict(result) == expected
    assert result["message"] == expected["message"]
    assert result.message == expected["message"]


@pytest.mark.parametrize(
    ("profile", "expected"),
    [
        (
            Profile(status="approved"),
            {
                "profile_status": "approved",
                "can_access_dashboard": True,
                "must_complete_profile": False,
                "can_submit_for_review": False,
                "marketplace_visible": True,
                "redirect_to": DASHBOARD_ROUTE,
                "message": "Your vendor profile is approved and visible in the marketplace.",
            },
        ),
        (
            Profile(status="pending_review"),
            {
                "profile_status": "pending_review",
                "can_access_dashboard": True,
                "must_complete_profile": False,
                "can_submit_for_review": False,
                "marketplace_visible": False,
                "redirect_to": DASHBOARD_ROUTE,
                "message": "Your profile is under review. Marketplace visibility starts after admin approval.",
            },
        ),
        (
            Profile(status="suspended"),
            {
                "profile_status": "suspended",
                "can_access_dashboard": False,
                "must_complete_profile": False,
                "can_submit_for_review": False,
                "marketplace_visible": False,
                "redirect_to": SETUP_ROUTE,
                "message": "Your vendor account is suspended. Please contact support.",
            },
        ),
        (
            Profile(status="rejected", rejection_reason="Add verification details."),
            {
                "profile_status": "rejected",
                "can_access_dashboard": False,
                "must_complete_profile": True,
                "can_submit_for_review": True,
                "marketplace_visible": False,
                "redirect_to": SETUP_ROUTE,
                "message": "Add verification details.",
            },
        ),
        (
            Profile(
                status="rejected",
                field_errors={"description": ["This field is required."]},
            ),
            {
                "profile_status": "rejected",
                "can_access_dashboard": False,
                "must_complete_profile": True,
                "can_submit_for_review": False,
                "marketplace_visible": False,
                "redirect_to": SETUP_ROUTE,
                "message": "Your vendor profile needs updates before resubmission.",
            },
        ),
        (
            Profile(status="draft"),
            {
                "profile_status": "draft",
                "can_access_dashboard": False,
                "must_complete_profile": True,
                "can_submit_for_review": True,
                "marketplace_visible": False,
                "redirect_to": SETUP_ROUTE,
                "message": "Submit your vendor profile for admin review.",
            },
        ),
        (
            Profile(
                status="draft",
                field_errors={"business_name": ["This field is required."]},
            ),
            {
                "profile_status": "incomplete",
                "can_access_dashboard": False,
                "must_complete_profile": True,
                "can_submit_for_review": False,
                "marketplace_visible": False,
                "redirect_to": SETUP_ROUTE,
                "message": "Complete your vendor profile before continuing.",
            },
        ),
    ],
)
def test_onboarding_status_and_completion_branches_preserve_exact_behavior(profile, expected):
    result = build_vendor_onboarding_contract(profile)

    assert isinstance(result, VendorOnboardingDTO)
    assert result == expected


def test_status_normalization_still_uses_string_conversion():
    result = build_vendor_onboarding_contract(Profile(status=StringStatus()))

    assert result.profile_status == "approved"
    assert result.can_access_dashboard is True
    assert result.redirect_to == DASHBOARD_ROUTE
