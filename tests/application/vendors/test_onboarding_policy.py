from types import SimpleNamespace

from application.vendors.onboarding_policy import (
    build_vendor_onboarding_contract,
    vendor_field_errors,
)
from domain.vendors.entities import VendorProfile, profile_completion_errors_for


PROFILE_CREATE_ACTION = {
    "method": "POST",
    "path": "/api/django/vendors/profile/",
}


def test_read_model_completion_errors_use_domain_required_fields(monkeypatch):
    required_fields = ("business_name", "service_area")
    monkeypatch.setattr(
        VendorProfile,
        "required_profile_fields",
        classmethod(lambda cls: required_fields),
    )
    read_model = SimpleNamespace(
        business_name="",
        service_area=" ",
        category="photography",
        description="A sufficiently detailed vendor description.",
        contact_email="vendor@example.com",
        contact_phone="+250788123456",
    )

    assert vendor_field_errors(read_model) == profile_completion_errors_for(read_model, required_fields)


def test_onboarding_action_points_missing_profile_to_real_profile_creation_endpoint():
    onboarding = build_vendor_onboarding_contract(None)

    assert onboarding.redirect_to == "COMPLETE_PROFILE"
    assert onboarding.action == PROFILE_CREATE_ACTION


def test_onboarding_action_points_incomplete_profile_to_real_profile_creation_endpoint():
    read_model = SimpleNamespace(
        status="draft",
        business_name="",
        service_area="Kigali",
        category="photography",
        description="A sufficiently detailed vendor description.",
        contact_email="vendor@example.com",
        contact_phone="+250788123456",
    )

    onboarding = build_vendor_onboarding_contract(read_model)

    assert onboarding.profile_status == "incomplete"
    assert onboarding.redirect_to == "COMPLETE_PROFILE"
    assert onboarding.action == PROFILE_CREATE_ACTION


def test_onboarding_action_is_none_when_profile_creation_is_not_the_next_step():
    complete_read_model = SimpleNamespace(
        status="draft",
        business_name="Studio One",
        service_area="Kigali",
        category="photography",
        description="A sufficiently detailed vendor description.",
        contact_email="vendor@example.com",
        contact_phone="+250788123456",
    )
    rejected_read_model = SimpleNamespace(
        status="rejected",
        rejection_reason=None,
        business_name="",
        service_area="Kigali",
        category="photography",
        description="A sufficiently detailed vendor description.",
        contact_email="vendor@example.com",
        contact_phone="+250788123456",
    )

    assert build_vendor_onboarding_contract(complete_read_model).action is None
    assert build_vendor_onboarding_contract(rejected_read_model).action is None
