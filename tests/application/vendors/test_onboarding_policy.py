from types import SimpleNamespace

from application.vendors.onboarding_policy import vendor_field_errors
from domain.vendors.entities import VendorProfile, profile_completion_errors_for


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

