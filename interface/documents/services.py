from infrastructure.repos.django_export_job_repository import DjangoExportJobRepository
from infrastructure.adapters.django_event_dispatcher import DjangoEventDispatcher
from application.documents.handlers import DocumentCommandHandlers, DocumentQueryHandlers


def get_command_handlers() -> DocumentCommandHandlers:
    """Return fully initialized DocumentCommandHandlers with all dependencies."""
    return DocumentCommandHandlers(
        job_repo=DjangoExportJobRepository(),
        event_dispatcher=DjangoEventDispatcher(),
    )


def get_query_handlers() -> DocumentQueryHandlers:
    """Return fully initialized DocumentQueryHandlers with all dependencies."""
    return DocumentQueryHandlers(
        job_repo=DjangoExportJobRepository(),
    )