# DRF URLs for Accounts Interface Layer

from django.urls import path
from .views.auth_views import LoginView, RegisterView
from .views.session_views import SessionView
from .views.device_views import DeviceView

urlpatterns = [
    path('auth/login/', LoginView.as_view(), name='login'),
    path('auth/register/', RegisterView.as_view(), name='register'),
    path('session/', SessionView.as_view(), name='session'),
    path('device/', DeviceView.as_view(), name='device'),
]
