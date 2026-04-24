from django.contrib import admin
from django.urls import path, include

urlpatterns = [
    path("admin/", admin.site.urls),
    path("api/django/identity/", include("django_app.identity.urls")),
    path("api/django/events/", include("django_app.events.urls")),
    path("api/django/vendors/", include("django_app.vendors.urls")),
    path("api/django/documents/", include("django_app.documents.urls")),
    path("api/django/governance/", include("django_app.governance.urls")),
    path("api/django/payments/", include("django_app.payments.urls")),
]