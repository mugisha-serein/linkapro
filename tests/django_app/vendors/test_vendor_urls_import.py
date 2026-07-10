from django.urls import reverse


def test_vendor_urlconf_imports_and_exposes_critical_routes():
    assert reverse("vendor-profile-status") == "/api/django/vendors/profile/status/"
    assert reverse("vendor-dashboard-summary") == "/api/django/vendors/dashboard-summary/"
    assert reverse("vendor-analytics") == "/api/django/vendors/analytics/"
    assert reverse("vendor-activity") == "/api/django/vendors/activity/"
