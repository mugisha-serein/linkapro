from django.urls import path
from .views import FlagContentCreateView

urlpatterns = [
    path("flags/", FlagContentCreateView.as_view(), name="flag-content"),
]