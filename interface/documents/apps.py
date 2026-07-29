from django.apps import AppConfig


class DocumentsConfig(AppConfig):
    default_auto_field = "django.db.models.BigAutoField"
    name = "interface.documents"
    label = "documents"

    def ready(self):
        import interface.documents.signals  # noqa: F401
