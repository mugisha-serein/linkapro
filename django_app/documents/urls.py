from django.urls import path
from .views import ExportRequestView, ExportJobStatusView

urlpatterns = [
    path("events/<uuid:event_id>/export/", ExportRequestView.as_view(), name="request-export"),
    path("jobs/<uuid:job_id>/", ExportJobStatusView.as_view(), name="export-job-status"),
]