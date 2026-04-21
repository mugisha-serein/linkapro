from rest_framework import serializers

from django_app.documents.models import ExportJob


class ExportRequestSerializer(serializers.Serializer):
    """Validate export request payload."""
    export_type = serializers.ChoiceField(
        choices=ExportJob.ExportType.choices,
        help_text="Type of document to export"
    )


class ExportJobSerializer(serializers.ModelSerializer):
    """Serialize export job status and details."""
    event_id = serializers.UUIDField(source="event.id", read_only=True)
    requested_by_email = serializers.EmailField(source="requested_by.email", read_only=True)

    class Meta:
        model = ExportJob
        fields = [
            "id",
            "event_id",
            "export_type",
            "status",
            "file_url",
            "error_message",
            "created_at",
            "updated_at",
            "requested_by_email",
        ]
        read_only_fields = fields