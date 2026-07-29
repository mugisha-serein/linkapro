from payments.infrastructure.factories import (
    build_payment_command_handlers,
    build_payment_query_handlers,
)
from payments.application.handlers import PaymentCommandHandlers
from payments.application.query_handlers import PaymentQueryHandlers


def get_command_handlers() -> PaymentCommandHandlers:
    return build_payment_command_handlers()


def get_query_handlers() -> PaymentQueryHandlers:
    return build_payment_query_handlers()
