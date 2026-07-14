from __future__ import annotations

from dataclasses import FrozenInstanceError, fields, is_dataclass
from enum import Enum
import inspect
import json
from typing import Mapping, Sequence, get_type_hints

import pytest

from application.vendors.profile import onboarding_policy
from application.vendors.profile.onboarding_policy import COMPLETE_PROFILE, DASHBOARD_ROUTE, OPEN_DASHBOARD, SETUP_ROUTE, VendorOnboardingDTO, VendorOnboardingRedirectIntent, build_vendor_onboarding_contract, vendor_field_errors
from application.vendors.profile.ports import ProfileCompletionErrors, VendorProfileCompletionProvider


class Profile:
    def __init__(
        self,
        *,
        status="draft",
        rejection_reason=None,
    ):
        self.status = status
        self.rejection_reason = rejection_reason


class CompletionProvider:
    def __init__(self, errors: Mapping[str, Sequence[str]] | None = None):
        self.errors = errors or {}
        self.calls = []

    def get_profile_completion_errors(self, profile: object) -> ProfileCompletionErrors:
        self.calls.append(profile)
        return self.errors


class StatusWithConflictingString:
    value = "approved"

    def __str__(self) -> str:
        return "rejected"


class VendorStatusValue(str, Enum):
    DRAFT = "draft"
    PENDING_REVIEW = "pending_review"
    APPROVED = "approved"
    REJECTED = "rejected"
    SUSPENDED = "suspended"


def _build(profile, *, errors=None, provider=None):
    provider = provider or CompletionProvider(errors)
    return build_vendor_onboarding_contract(profile, provider), provider


def test_profile_completion_provider_port_is_the_typed_completion_contract():
    hints = get_type_hints(
        VendorProfileCompletionProvider.get_profile_completion_errors
    )

    assert hints["profile"] is object
    assert hints["return"] == Mapping[str, Sequence[str]]


def test_onboarding_requires_an_explicit_completion_provider():
    with pytest.raises(TypeError, match="completion_provider"):
        build_vendor_onboarding_contract(Profile())

    with pytest.raises(TypeError, match="completion_provider"):
        vendor_field_errors(Profile())


def test_onboarding_contains_no_fallback_profile_completion_rules():
    source = inspect.getsource(onboarding_policy)

    assert not hasattr(onboarding_policy, "_profile_completion_errors")
    assert '"business_name"' not in source
    assert '"category"' not in source
    assert '"description"' not in source
    assert '"service_area"' not in source
    assert '"contact_email"' not in source
    assert '"contact_phone"' not in source
    assert '"custom_category"' not in source


def test_vendor_field_errors_uses_only_the_provider_and_preserves_existing_shape():
    profile = Profile()
    provider = CompletionProvider(
        {
            "business_name": ("This field is required.",),
            "description": ["Use at least 20 characters."],
        }
    )

    errors = vendor_field_errors(profile, provider)

    assert errors == {
        "business_name": ["This field is required."],
        "description": ["Use at least 20 characters."],
    }
    assert provider.calls == [profile]


def test_profile_owned_completion_method_is_not_used_as_a_fallback():
    class ProfileWithForbiddenFallback(Profile):
        def get_profile_completion_errors(self):
            raise AssertionError("Profile completion fallback must not be called.")

    profile = ProfileWithForbiddenFallback(status="draft")
    provider = CompletionProvider({})

    result = build_vendor_onboarding_contract(profile, provider)

    assert result.profile_status == "draft"
    assert result.can_submit_for_review is True
    assert provider.calls == [profile]


def test_missing_profile_does_not_request_completion_errors():
    provider = CompletionProvider({"business_name": ["Required"]})

    result = build_vendor_onboarding_contract(None, provider)

    assert result.profile_status == "missing"
    assert result.redirect_to is COMPLETE_PROFILE
    assert provider.calls == []
    assert vendor_field_errors(None, provider) == {}
    assert provider.calls == []


def test_onboarding_redirect_intents_are_typed_and_contain_no_frontend_routes():
    assert tuple(VendorOnboardingRedirectIntent) == (
        VendorOnboardingRedirectIntent.COMPLETE_PROFILE,
        VendorOnboardingRedirectIntent.OPEN_DASHBOARD,
    )
    assert COMPLETE_PROFILE is VendorOnboardingRedirectIntent.COMPLETE_PROFILE
    assert OPEN_DASHBOARD is VendorOnboardingRedirectIntent.OPEN_DASHBOARD
    assert SETUP_ROUTE is COMPLETE_PROFILE
    assert DASHBOARD_ROUTE is OPEN_DASHBOARD
    assert str(COMPLETE_PROFILE) == "COMPLETE_PROFILE"
    assert str(OPEN_DASHBOARD) == "OPEN_DASHBOARD"


def test_vendor_onboarding_dto_is_frozen_and_has_exact_typed_fields():
    assert is_dataclass(VendorOnboardingDTO)
    assert tuple(field.name for field in fields(VendorOnboardingDTO)) == (
        "profile_status",
        "can_access_dashboard",
        "must_complete_profile",
        "can_submit_for_review",
        "marketplace_visible",
        "redirect_to",
        "action",
        "message",
    )
    assert get_type_hints(VendorOnboardingDTO) == {
        "profile_status": str,
        "can_access_dashboard": bool,
        "must_complete_profile": bool,
        "can_submit_for_review": bool,
        "marketplace_visible": bool,
        "redirect_to": VendorOnboardingRedirectIntent,
        "action": dict[str, str] | None,
        "message": str,
    }

    dto, _ = _build(None)
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
    dto, _ = _build(None)

    with pytest.raises(TypeError, match="VendorOnboardingDTO is immutable"):
        mutation(dto)


def test_missing_profile_preserves_exact_contract_and_dictionary_behavior():
    result, _ = _build(None)
    expected = {
        "profile_status": "missing",
        "can_access_dashboard": False,
        "must_complete_profile": True,
        "can_submit_for_review": False,
        "marketplace_visible": False,
        "redirect_to": COMPLETE_PROFILE,
        "action": {"method": "POST", "path": "/api/django/vendors/profile/"},
        "message": "Complete your vendor profile before continuing.",
    }

    assert isinstance(result, VendorOnboardingDTO)
    assert isinstance(result, dict)
    assert result == expected
    assert dict(result) == expected
    assert result["message"] == expected["message"]
    assert result.message == expected["message"]
    assert result.redirect_to is COMPLETE_PROFILE
    assert json.loads(json.dumps(result))["redirect_to"] == "COMPLETE_PROFILE"


@pytest.mark.parametrize(
    ("profile", "errors", "expected"),
    [
        (
            Profile(status="approved"),
            {},
            {
                "profile_status": "approved",
                "can_access_dashboard": True,
                "must_complete_profile": False,
                "can_submit_for_review": False,
                "marketplace_visible": True,
                "redirect_to": OPEN_DASHBOARD,
                "action": None,
                "message": "Your vendor profile is approved and visible in the marketplace.",
            },
        ),
        (
            Profile(status="pending_review"),
            {"business_name": ["Required"]},
            {
                "profile_status": "pending_review",
                "can_access_dashboard": True,
                "must_complete_profile": False,
                "can_submit_for_review": False,
                "marketplace_visible": False,
                "redirect_to": OPEN_DASHBOARD,
                "action": None,
                "message": "Your profile is under review. Marketplace visibility starts after admin approval.",
            },
        ),
        (
            Profile(status="suspended"),
            {},
            {
                "profile_status": "suspended",
                "can_access_dashboard": False,
                "must_complete_profile": False,
                "can_submit_for_review": False,
                "marketplace_visible": False,
                "redirect_to": COMPLETE_PROFILE,
                "action": None,
                "message": "Your vendor account is suspended. Please contact support.",
            },
        ),
        (
            Profile(status="rejected", rejection_reason="Add verification details."),
            {},
            {
                "profile_status": "rejected",
                "can_access_dashboard": False,
                "must_complete_profile": True,
                "can_submit_for_review": True,
                "marketplace_visible": False,
                "redirect_to": COMPLETE_PROFILE,
                "action": None,
                "message": "Add verification details.",
            },
        ),
        (
            Profile(status="rejected"),
            {"description": ["This field is required."]},
            {
                "profile_status": "rejected",
                "can_access_dashboard": False,
                "must_complete_profile": True,
                "can_submit_for_review": False,
                "marketplace_visible": False,
                "redirect_to": COMPLETE_PROFILE,
                "action": None,
                "message": "Your vendor profile needs updates before resubmission.",
            },
        ),
        (
            Profile(status="draft"),
            {},
            {
                "profile_status": "draft",
                "can_access_dashboard": False,
                "must_complete_profile": True,
                "can_submit_for_review": True,
                "marketplace_visible": False,
                "redirect_to": COMPLETE_PROFILE,
                "action": None,
                "message": "Submit your vendor profile for admin review.",
            },
        ),
        (
            Profile(status="draft"),
            {"business_name": ["This field is required."]},
            {
                "profile_status": "incomplete",
                "can_access_dashboard": False,
                "must_complete_profile": True,
                "can_submit_for_review": False,
                "marketplace_visible": False,
                "redirect_to": COMPLETE_PROFILE,
                "action": {"method": "POST", "path": "/api/django/vendors/profile/"},
                "message": "Complete your vendor profile before continuing.",
            },
        ),
    ],
)
def test_onboarding_status_and_completion_branches_preserve_exact_behavior(
    profile,
    errors,
    expected,
):
    result, provider = _build(profile, errors=errors)

    assert isinstance(result, VendorOnboardingDTO)
    assert isinstance(result.redirect_to, VendorOnboardingRedirectIntent)
    assert result == expected
    assert provider.calls == [profile]


def test_status_normalization_prefers_value_over_string_conversion():
    result, _ = _build(Profile(status=StatusWithConflictingString()))

    assert result.profile_status == "approved"
    assert result.can_access_dashboard is True
    assert result.redirect_to is OPEN_DASHBOARD


@pytest.mark.parametrize("status", tuple(VendorStatusValue))
def test_status_normalization_accepts_supported_enum_values(status):
    result, _ = _build(Profile(status=status))

    assert result.profile_status == status.value


@pytest.mark.parametrize(
    ("status", "expected"),
    [
        (" APPROVED ", "approved"),
        ("Pending_Review", "pending_review"),
        (None, "draft"),
        ("", "draft"),
        ("   ", "draft"),
    ],
)
def test_status_normalization_normalizes_supported_strings_and_preserves_draft_fallback(
    status,
    expected,
):
    result, _ = _build(Profile(status=status))

    assert result.profile_status == expected


@pytest.mark.parametrize(
    "status",
    ["archived", "incomplete", "missing", 7, object()],
)
def test_status_normalization_rejects_unsupported_statuses(status):
    with pytest.raises(ValueError, match="Unsupported vendor status"):
        _build(Profile(status=status))


def test_invalid_status_is_rejected_before_completion_provider_runs():
    profile = Profile(status="archived")
    provider = CompletionProvider()

    with pytest.raises(ValueError, match="Unsupported vendor status: archived"):
        build_vendor_onboarding_contract(profile, provider)

    assert provider.calls == []
