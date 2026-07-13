from types import SimpleNamespace

from infrastructure.repos.django_vendor_read_repository import DjangoVendorReadRepository


def _profile(**overrides):
    data = {
        "business_name": "Kigali Events",
        "category": "photography",
        "custom_category": None,
        "description": "Professional event coverage across Kigali.",
        "service_area": "Kigali",
        "contact_email": "vendor@example.com",
        "contact_phone": "+250788123456",
    }
    data.update(overrides)
    return SimpleNamespace(**data)


def test_dashboard_completion_percentage_keeps_domain_completeness_meaning_with_bonus_math():
    complete_profile = _profile()
    incomplete_other_profile = _profile(category="other", custom_category="")

    assert DjangoVendorReadRepository.strict_profile_completion_errors(complete_profile) == {}
    assert DjangoVendorReadRepository.dashboard_completion_percentage(
        complete_profile,
        portfolio_count=0,
        package_count=0,
    ) == 75

    strict_errors = DjangoVendorReadRepository.strict_profile_completion_errors(incomplete_other_profile)

    assert strict_errors == {"custom_category": ["Tell us what service you provide when choosing Other."]}
    assert DjangoVendorReadRepository.dashboard_completion_percentage(
        incomplete_other_profile,
        portfolio_count=1,
        package_count=1,
    ) < 100
