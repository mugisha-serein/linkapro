from django.urls import path
from .views import (
    RegisterView,
    LoginView,
    TokenRefreshView,
    TokenRevokeView,
    EnableTwoFactorView,
    VerifyTwoFactorSetupView,
    LoginTwoFactorView,
    ProfileView,
    GoogleLoginView,
    GoogleCallbackView,
    SetupPasswordView,
    ForgotPasswordView,
    ResetPasswordView,
)

urlpatterns = [
    path("register/", RegisterView.as_view(), name="register"),
    path("login/", LoginView.as_view(), name="login"),
    path("profile/", ProfileView.as_view(), name="profile"),
    path("users/me/", ProfileView.as_view(), name="users-me"),
    path("setup-password/", SetupPasswordView.as_view(), name="setup-password"),
    path("forgot-password/", ForgotPasswordView.as_view(), name="forgot-password"),
    path("reset-password/", ResetPasswordView.as_view(), name="reset-password"),
    path("token/refresh/", TokenRefreshView.as_view(), name="token-refresh"),
    path("token/revoke/", TokenRevokeView.as_view(), name="token-revoke"),
    
    path("2fa/enable/", EnableTwoFactorView.as_view(), name="2fa-enable"),
    path("2fa/verify-setup/", VerifyTwoFactorSetupView.as_view(), name="2fa-verify-setup"),
    path("2fa/login/", LoginTwoFactorView.as_view(), name="2fa-login"),
    
    path("auth/google/", GoogleLoginView.as_view(), name="google-login"),
    path("auth/google/callback/", GoogleCallbackView.as_view(), name="google-callback"),
]
