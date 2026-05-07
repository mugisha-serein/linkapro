# django_app/identity/oauth_urls.py

from django.urls import path
from .views import GoogleLoginView, GoogleCallbackView

urlpatterns = [
    path("google/", GoogleLoginView.as_view(), name="google-login"),
    path("google/callback/", GoogleCallbackView.as_view(), name="google-callback"),
]