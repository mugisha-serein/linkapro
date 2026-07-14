from __future__ import annotations

from application.vendors.shared.handlers import VendorCommandHandlers
from application.vendors.shared.query_handlers import VendorQueryHandlers
from application.vendors.inquiries.ports import InquiryAbuseProtectionPort
from application.vendors.portfolio.ports import PortfolioImageCreationPort
from application.vendors.shared.ports import VendorAggregateUnitOfWork, VendorAuthorizationPort
from infrastructure.adapters.django_vendor_idempotency import DjangoVendorIdempotencyAdapter
from infrastructure.repos.inquiries.django_repository import DjangoInquiryRepository
from infrastructure.repos.packages.django_repository import DjangoServicePackageRepository
from infrastructure.repos.portfolio.django_creation import DjangoPortfolioImageCreationPort
from infrastructure.repos.portfolio.django_reorder_uow import DjangoPortfolioReorderUnitOfWork
from infrastructure.repos.portfolio.django_repository import DjangoPortfolioImageRepository
from infrastructure.repos.profile.django_aggregate_uow import DjangoVendorAggregateUnitOfWork
from infrastructure.repos.profile.django_read_repository import DjangoVendorReadRepository
from infrastructure.repos.profile.django_repository import DjangoVendorProfileRepository

from .adapters import DjangoInquiryAbuseProtectionAdapter, DjangoVendorAuthorizationAdapter


def get_command_handlers(
    *,
    aggregate_uow: VendorAggregateUnitOfWork | None = None,
    authorization_port: VendorAuthorizationPort | None = None,
    inquiry_abuse_protection_port: InquiryAbuseProtectionPort | None = None,
    portfolio_creation_port: PortfolioImageCreationPort | None = None,
) -> VendorCommandHandlers:
    """Build the production vendor command composition with explicit override seams."""
    resolved_uow = aggregate_uow or DjangoVendorAggregateUnitOfWork()
    resolved_authorization = authorization_port or DjangoVendorAuthorizationAdapter()
    resolved_abuse_protection = (
        inquiry_abuse_protection_port or DjangoInquiryAbuseProtectionAdapter()
    )
    resolved_creation = portfolio_creation_port or DjangoPortfolioImageCreationPort(
        aggregate_uow=resolved_uow
    )

    return VendorCommandHandlers(
        vendor_repo=DjangoVendorProfileRepository(),
        image_repo=DjangoPortfolioImageRepository(),
        package_repo=DjangoServicePackageRepository(),
        inquiry_repo=DjangoInquiryRepository(),
        reorder_uow=DjangoPortfolioReorderUnitOfWork(),
        aggregate_uow=resolved_uow,
        authorization_port=resolved_authorization,
        idempotency_port=DjangoVendorIdempotencyAdapter(),
        inquiry_abuse_protection_port=resolved_abuse_protection,
        portfolio_creation_port=resolved_creation,
    )


def get_query_handlers(
    *,
    authorization_port: VendorAuthorizationPort | None = None,
) -> VendorQueryHandlers:
    """Build the production vendor query composition with authorization enabled."""
    return VendorQueryHandlers(
        vendor_repo=DjangoVendorProfileRepository(),
        image_repo=DjangoPortfolioImageRepository(),
        inquiry_repo=DjangoInquiryRepository(),
        read_repo=DjangoVendorReadRepository(),
        authorization_port=authorization_port or DjangoVendorAuthorizationAdapter(),
        package_repo=DjangoServicePackageRepository(),
    )
