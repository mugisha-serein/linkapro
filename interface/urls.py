from django.contrib import admin
from django.urls import path, include
from interface.documents.views import ExportJobStatusView, ExportRequestView

urlpatterns = [
    path("admin/", admin.site.urls),
    path("api/django/identity/", include("interface.identity.urls")),
    path("api/django/events/<uuid:event_id>/export/", ExportRequestView.as_view(), name="event-export-alias"),
    path("api/django/exports/<uuid:job_id>/", ExportJobStatusView.as_view(), name="export-job-status-alias"),
    path("api/django/events/", include("interface.events.urls")),
    path("api/django/vendors/", include("interface.vendors.urls")),
    path("api/django/documents/", include("interface.documents.urls")),
    path("api/django/governance/", include("interface.governance.urls")),
    path("api/django/payments/", include("interface.payments.urls")),
]
