from django.urls import path
from .views import FlagContentCreateView, AdminMetricsView

urlpatterns = [
    path("flags/", FlagContentCreateView.as_view(), name="flag-content"),
    path("metrics/", AdminMetricsView.as_view(), name="admin-metrics"),
]