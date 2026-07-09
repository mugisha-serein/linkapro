from __future__ import annotations

from .dtos import VendorProfileDTO
from .handlers import VendorCommandHandlers
from .vendor_branding_commands import UpdateVendorBrandingMediaCommand


def update_vendor_branding_media(
    self: VendorCommandHandlers,
    cmd: UpdateVendorBrandingMediaCommand,
) -> VendorProfileDTO:
    self._assert_actor_owns_vendor(cmd.actor, cmd.vendor_id)
    profile = self._get_vendor_or_raise(cmd.vendor_id)
    self._assert_expected_version(profile.id, profile.version, cmd.expected_version)
    original_version = profile.version
    profile.update_details(
        profile_image_url=cmd.profile_image_url,
        profile_image_public_id=cmd.profile_image_public_id,
        cover_image_url=cmd.cover_image_url,
        cover_image_public_id=cmd.cover_image_public_id,
    )
    return self._save_if_changed(profile, original_version, self._to_profile_dto)


VendorCommandHandlers.update_vendor_branding_media = update_vendor_branding_media
