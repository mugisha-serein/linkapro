import uuid
from types import SimpleNamespace

from infrastructure.repos.profile.django_read_repository import DjangoVendorReadRepository


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


def test_analytics_builds_dto_from_normalized_metrics_mapping():
    class MetricsReadRepository(DjangoVendorReadRepository):
        def vendor_metrics(self, vendor_id):
            return {
                "profile_completion": 100,
                "total_inquiries": 3,
                "inquiries_mtd": 2,
                "unread_inquiries": 1,
                "read_inquiries": 2,
                "response_rate": 67,
                "total_packages": 4,
                "active_packages": 1,
                "approved_packages": 1,
                "pending_packages": 2,
                "rejected_packages": 1,
                "portfolio_count": 5,
                "account_status": "approved",
                "service_area": "Kigali",
            }

    analytics = MetricsReadRepository().analytics(uuid.uuid4())

    assert analytics.response_rate == 66.67
    assert analytics.avg_response_time_hours is None
    assert analytics.conversion_rate is None
    assert analytics.unavailable_metrics == ("avg_response_time_hours", "conversion_rate")
