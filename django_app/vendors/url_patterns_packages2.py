from django.urls import path
from . import contract_views as c
urlpatterns = [
    path("packages/", c.ServicePackageListView.as_view(), name="package-list"),
    path("packages/<uuid:package_id>/", c.ServicePackageDetailView.as_view(), name="package-detail"),
    path("packages/<uuid:package_id>/activate/", c.ServicePackageActivateView.as_view(), name="package-activate"),
]
