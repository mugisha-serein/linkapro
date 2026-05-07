from django.urls import path
from rest_framework_simplejwt.views import TokenRefreshView
from .views import (
    RegisterView,
    LoginView,
    EnableTwoFactorView,
    VerifyTwoFactorSetupView,
    LoginTwoFactorView,
    ProfileView,
    GoogleLoginView,
    GoogleCallbackView,
)

urlpatterns = [
    path("register/", RegisterView.as_view(), name="register"),
    path("login/", LoginView.as_view(), name="login"),
    path("profile/", ProfileView.as_view(), name="profile"),
    path("users/me/", ProfileView.as_view(), name="users-me"),
    path("token/refresh/", TokenRefreshView.as_view(), name="token-refresh"),
    
    path("2fa/enable/", EnableTwoFactorView.as_view(), name="2fa-enable"),
    path("2fa/verify-setup/", VerifyTwoFactorSetupView.as_view(), name="2fa-verify-setup"),
    path("2fa/login/", LoginTwoFactorView.as_view(), name="2fa-login"),
    
    path("auth/google/", GoogleLoginView.as_view(), name="google-login"),
    path("auth/google/callback/", GoogleCallbackView.as_view(), name="google-callback"),
]
