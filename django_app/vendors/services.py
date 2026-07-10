from infrastructure.repos.django_vendor_profile_repository import DjangoVendorProfileRepository
from infrastructure.repos.django_portfolio_image_repository import DjangoPortfolioImageRepository
from infrastructure.repos.django_service_package_repository import DjangoServicePackageRepository
from infrastructure.repos.django_inquiry_repository import DjangoInquiryRepository
from infrastructure.repos.django_portfolio_reorder_uow import DjangoPortfolioReorderUnitOfWork
from infrastructure.repos.django_vendor_read_repository import DjangoVendorReadRepository
from infrastructure.adapters.django_vendor_idempotency import DjangoVendorIdempotencyAdapter
from application.vendors.errors import VendorApplicationConfigurationError
from application.vendors.handlers import VendorCommandHandlers, VendorQueryHandlers
from application.vendors.ports import (
    InquiryAbuseProtectionPort,
    PortfolioImageCreationPort,
    VendorAggregateUnitOfWork,
    VendorAuthorizationPort,
)


def get_command_handlers(
    *,
    aggregate_uow: VendorAggregateUnitOfWork,
    authorization_port: VendorAuthorizationPort,
    inquiry_abuse_protection_port: InquiryAbuseProtectionPort,
    portfolio_creation_port: PortfolioImageCreationPort | None = None,
) -> VendorCommandHandlers:
    """Return fully initialized VendorCommandHandlers with all dependencies."""
    if portfolio_creation_port is None:
        raise VendorApplicationConfigurationError(
            field_errors={"portfolio_creation_port": ["Portfolio image creation port is required."]}
        )
    image_repo = DjangoPortfolioImageRepository()
    return VendorCommandHandlers(
        vendor_repo=DjangoVendorProfileRepository(),
        image_repo=image_repo,
        package_repo=DjangoServicePackageRepository(),
        inquiry_repo=DjangoInquiryRepository(),
        aggregate_uow=aggregate_uow,
        authorization_port=authorization_port,
        idempotency_port=DjangoVendorIdempotencyAdapter(),
        inquiry_abuse_protection_port=inquiry_abuse_protection_port,
        reorder_uow=DjangoPortfolioReorderUnitOfWork(),
        portfolio_creation_port=portfolio_creation_port,
    )


def get_query_handlers() -> VendorQueryHandlers:
    """Return fully initialized VendorQueryHandlers with all dependencies."""
    return VendorQueryHandlers(
        vendor_repo=DjangoVendorProfileRepository(),
        image_repo=DjangoPortfolioImageRepository(),
        inquiry_repo=DjangoInquiryRepository(),
        read_repo=DjangoVendorReadRepository(),
    )
