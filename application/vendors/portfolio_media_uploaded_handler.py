from __future__ import annotations

from .dtos import PortfolioImageDTO
from .errors import VendorResourceNotFound
from .handlers import VendorCommandHandlers
from .portfolio_media_commands import MarkPortfolioMediaUploadedCommand


def mark_portfolio_media_uploaded(
    self: VendorCommandHandlers,
    cmd: MarkPortfolioMediaUploadedCommand,
) -> PortfolioImageDTO:
    self._assert_actor_owns_vendor(cmd.actor, cmd.vendor_id)
    media = self.image_repo.get_for_vendor(cmd.vendor_id, cmd.media_id)
    if not media:
        raise VendorResourceNotFound("Image not found.")
    self._assert_expected_version(media.id, media.version, cmd.expected_version)
    original_version = media.version
    media.mark_uploaded(public_id=cmd.public_id, secure_url=cmd.secure_url)
    return self._save_if_changed(media, original_version, self._to_image_dto)


VendorCommandHandlers.mark_portfolio_media_uploaded = mark_portfolio_media_uploaded
