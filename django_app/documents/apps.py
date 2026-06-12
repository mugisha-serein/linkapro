from django.apps import AppConfig


class DocumentsConfig(AppConfig):
    default_auto_field = "django.db.models.BigAutoField"
    name = "django_app.documents"
    label = "documents"

    def ready(self):
        import django_app.documents.signals  # noqa: F401
