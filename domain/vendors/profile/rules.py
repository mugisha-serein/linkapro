from __future__ import annotations

from domain.vendors.profile.entity import VendorProfile, VendorStatus


def is_draft_incomplete(profile: VendorProfile) -> bool:
    return profile.status == VendorStatus.DRAFT and bool(profile.get_profile_completion_errors())


def is_pending_review(profile: VendorProfile) -> bool:
    return profile.status == VendorStatus.PENDING_REVIEW
