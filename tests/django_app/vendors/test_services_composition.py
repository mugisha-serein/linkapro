from __future__ import annotations

from application.vendors.handlers import VendorCommandHandlers, VendorQueryHandlers
from django_app.vendors.adapters import (
    DjangoInquiryAbuseProtectionAdapter,
    DjangoVendorAuthorizationAdapter,
)
from django_app.vendors.services import get_command_handlers, get_query_handlers
from infrastructure.repos.django_portfolio_image_creation