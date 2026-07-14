from types import SimpleNamespace

from application.vendors.profile.handlers import ProfileQueryHandlersMixin
from application.vendors.profile.queries import GetVendorOnboardingStateQuery
from application.vendors.shared.commands import AuthenticatedActor
from domain.vendors.profile.entity import VendorStatus
from domain.vendors.profile.rules import is_draft_incomplete, is_pending_review


PROFILE_CREATE_ACTION = {
    "method": "POST",
    "path": "/api/django/vendors/profile/",
}


class Repo:
    def __init__(self, profile):
        self.profile = profile

    def get_by_user_id(self, user_id):
        return self.profile


class Handler(ProfileQueryHandlersMixin):
    def __init__(self, profile):
        self.vendor_repo = Repo(profile)


def profile(status=VendorStatus.DRAFT, completion_errors=None):
    return SimpleNamespace(
        status=status,
        get_profile_completion_errors=lambda: completion_errors or {},
    )


def query():
    return GetVendorOnboardingStateQuery(actor=AuthenticatedActor(user_id=__import__("uuid").uuid4()))


def test_profile_rules_name_draft_incomplete_and_pending_review_states():
    incomplete = profile(completion_errors={"business_name": ["This field is required."]})
    pending = profile(status=VendorStatus.PENDING_REVIEW)

    assert is_draft_incomplete(incomplete) is True
    assert is_pending_review(pending) is True


def test_missing_profile_state_points_to_real_profile_creation_endpoint():
    state = Handler(None).get_vendor_onboarding_state(query())

    assert state == {
        "profile_status": "missing",
        "can_access_dashboard": False,
        "must_complete_profile": True,
        "can_submit_for_review": False,
        "marketplace_visible": False,
        "action": PROFILE_CREATE_ACTION,
    }


def test_draft_incomplete_state_uses_status_and_real_action_path():
    state = Handler(profile(completion_errors={"description": ["Required"]})).get_vendor_onboarding_state(query())

    assert state["profile_status"] == "draft"
    assert state["can_submit_for_review"] is False
    assert state["action"] == PROFILE_CREATE_ACTION


def test_pending_review_state_is_read_only_and_hidden_from_marketplace():
    state = Handler(profile(status=VendorStatus.PENDING_REVIEW)).get_vendor_onboarding_state(query())

    assert state == {
        "profile_status": "pending_review",
        "can_access_dashboard": True,
        "must_complete_profile": False,
        "can_submit_for_review": False,
        "marketplace_visible": False,
        "action": None,
    }
