from application.vendors.analytics.handlers import AnalyticsQueryHandlersMixin
from application.vendors.inquiries.handlers import InquiryCommandHandlersMixin, InquiryQueryHandlersMixin
from application.vendors.packages.handlers import PackageCommandHandlersMixin, PackageQueryHandlersMixin
from application.vendors.portfolio.handlers import PortfolioCommandHandlersMixin, PortfolioQueryHandlersMixin
from application.vendors.profile.handlers import (
    ProfileCommandHandlersMixin,
    ProfileQueryHandlersMixin,
    _translate_profile_update_validation,
)
from application.vendors.shared.handlers import BaseVendorCommandHandler
from application.vendors.shared.query_handlers import BaseVendorQueryHandler


class VendorCommandHandlers(
    ProfileCommandHandlersMixin,
    PortfolioCommandHandlersMixin,
    PackageCommandHandlersMixin,
    InquiryCommandHandlersMixin,
    BaseVendorCommandHandler,
):
    def queue_portfolio_media(self, cmd):
        return PortfolioCommandHandlersMixin.queue_portfolio_media(self, cmd)

    def mark_portfolio_media_processing(self, cmd):
        return PortfolioCommandHandlersMixin.mark_portfolio_media_processing(self, cmd)

    def mark_portfolio_media_uploaded(self, cmd):
        return PortfolioCommandHandlersMixin.mark_portfolio_media_uploaded(self, cmd)

    def update_portfolio_caption(self, cmd):
        return PortfolioCommandHandlersMixin.update_portfolio_caption(self, cmd)

    def update_vendor_branding_media(self, cmd):
        return ProfileCommandHandlersMixin.update_vendor_branding_media(self, cmd)


class VendorQueryHandlers(
    ProfileQueryHandlersMixin,
    PortfolioQueryHandlersMixin,
    PackageQueryHandlersMixin,
    InquiryQueryHandlersMixin,
    AnalyticsQueryHandlersMixin,
    BaseVendorQueryHandler,
):
    pass


__all__ = ["VendorCommandHandlers", "VendorQueryHandlers", "_translate_profile_update_validation"]
