from __future__ import annotations

from domain.vendors.profile.entity import VendorProfile, VendorStatus, profile_completion_errors_for


def get_profile_completion_errors(profile: object) -> dict[str, list[str]]:
    return profile_completion_errors_for(profile, VendorProfile.required_profile_fields())


def is_draft_incomplete(profile: VendorProfile) -> bool:
    return profile.status == VendorStatus.DRAFT and bool(get_profile_completion_errors(profile))


def is_pending_review(profile: VendorProfile) -> bool:
    return profile.status == VendorStatus.PENDING_REVIEW
