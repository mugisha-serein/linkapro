from application.vendors.dtos import VendorProfileDTO
from application.vendors.onboarding_policy import (
    build_vendor_onboarding_contract,
    vendor_field_errors,
)


def _profile(**overrides):
    data = {
        "id": __import__("uuid").uuid4(),
        "user_id": __import__("uuid").uuid4(),
        "business_name": "Studio One",
        "category": "photography",
        "description": "Professional event photography services.",
        "service_area": "Kigali",
        "contact_email": "vendor@example.com",
        "contact_phone": "+250788000000",
        "custom_category": None,
        "website": None,
        "profile_image_url": None,
        "cover_image_url": None,
        "status": "draft",
        "submitted_at": None,
        "approved_at": None,
        "rejected_at": None,
        "rejection_reason": None,
        "version": 0,
    }
    data.update(overrides)
    return VendorProfileDTO(**data)


def test_real_vendor_profile_projection_uses_domain_completion_policy_when_provider_is_omitted():
    profile = _profile(description="short")

    errors = vendor_field_errors(profile)
    onboarding = build_vendor_onboarding_contract(profile)

    assert errors == {"description": ["Use at least 20 characters for your description."]}
    assert onboarding.profile_status == "incomplete"
    assert onboarding.can_submit_for_review is False


def test_complete_vendor_profile_projection_can_be_submitted_when_provider_is_omitted():
    onboarding = build_vendor_onboarding_contract(_profile())

    assert onboarding.profile_status == "draft"
    assert onboarding.can_submit_for_review is True


def test_generic_profile_still_requires_explicit_completion_provider():
    class GenericProfile:
        status = "draft"

    try:
        vendor_field_errors(GenericProfile())
    except TypeError as exc:
        assert "completion_provider" in str(exc)
    else:
        raise AssertionError("Generic profiles must require an explicit completion provider.")
