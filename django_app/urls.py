from django.contrib import admin
from django.urls import path, include
from django_app.documents.views import ExportJobStatusView, ExportRequestView

urlpatterns = [
    path("admin/", admin.site.urls),
    path("api/django/identity/", include("django_app.identity.urls")),
    path("api/django/events/<uuid:event_id>/export/", ExportRequestView.as_view(), name="event-export-alias"),
    path("api/django/exports/<uuid:job_id>/", ExportJobStatusView.as_view(), name="export-job-status-alias"),
    path("api/django/events/", include("django_app.events.urls")),
    path("api/django/vendors/", include("django_app.vendors.urls")),
    path("api/django/documents/", include("django_app.documents.urls")),
    path("api/django/governance/", include("django_app.governance.urls")),
    path("api/django/payments/", include("django_app.payments.urls")),
]
