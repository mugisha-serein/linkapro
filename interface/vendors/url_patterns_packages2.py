from django.urls import path
from .views import packages as v
urlpatterns = [
    path("packages/", v.ServicePackageListView.as_view(), name="package-list"),
    path("packages/<uuid:package_id>/", v.ServicePackageDetailView.as_view(), name="package-detail"),
    path("packages/<uuid:package_id>/activate/", v.ServicePackageActivateView.as_view(), name="package-activate"),
]
