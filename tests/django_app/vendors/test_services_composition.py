from __future__ import annotations

from application.vendors.shared.handlers import VendorCommandHandlers
from application.vendors.shared.query_handlers import VendorQueryHandlers
from django_app.vendors.adapters import (
    DjangoInquiryAbuseProtectionAdapter,
    DjangoVendorAuthorizationAdapter,
)
from django_app.vendors.services import get_command_handlers, get_query_handlers
from infrastructure.repos.portfolio.django_creation import DjangoPortfolioImageCreationPort
from infrastructure.repos.profile.django_aggregate_uow import DjangoVendorAggregateUnitOfWork


def test_command_handlers_use_complete_production_composition():
    handlers = get_command_handlers()

    assert isinstance(handlers, VendorCommandHandlers)
    assert isinstance(handlers.aggregate_uow, DjangoVendorAggregateUnitOfWork)
    assert isinstance(handlers.authorization_port, DjangoVendorAuthorizationAdapter)
    assert isinstance(
        handlers.inquiry_abuse_protection_port,
        DjangoInquiryAbuseProtectionAdapter,
    )
    assert isinstance(handlers.portfolio_creation_port, DjangoPortfolioImageCreationPort)


def test_query_handlers_include_production_authorization():
    handlers = get_query_handlers()

    assert isinstance(handlers, VendorQueryHandlers)
    assert isinstance(handlers.authorization_port, DjangoVendorAuthorizationAdapter)


def test_service_composition_keeps_explicit_override_seams():
    class AggregateUow:
        def add_with_pending_events(self, aggregate):
            return aggregate

        def save_with_pending_events(self, aggregate, *, expected_version):
            return aggregate

    class Authorization:
        def assert_actor_owns_vendor(self, actor, vendor_id):
            return None

        def assert_actor_can_access_vendor(self, actor, vendor_id):
            return None

        def assert_moderator_can_moderate_vendor(self, moderator, vendor_id):
            return None

    class AbuseProtection:
        def assert_inquiry_allowed(self, **kwargs):
            return None

    class PortfolioCreation:
        def create_at_next_order(self, *, vendor_id, image_factory):
            return image_factory(0)

    uow = AggregateUow()
    authorization = Authorization()
    abuse = AbuseProtection()
    creation = PortfolioCreation()

    handlers = get_command_handlers(
        aggregate_uow=uow,
        authorization_port=authorization,
        inquiry_abuse_protection_port=abuse,
        portfolio_creation_port=creation,
    )

    assert handlers.aggregate_uow is uow
    assert handlers.authorization_port is authorization
    assert handlers.inquiry_abuse_protection_port is abuse
    assert handlers.portfolio_creation_port is creation
