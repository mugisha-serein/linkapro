from django.urls import path
from .views import (
    RegisterView,
    LoginView,
    EnableTwoFactorView,
    VerifyTwoFactorSetupView,
    LoginTwoFactorView,
    ProfileView,
    GoogleLoginView,
    GoogleCallbackView,
    ForgotPasswordView,
)
from .secure_password_views import (
    SessionRevokingResetPasswordView,
    SessionRevokingSetupPasswordView,
)
from .session_views import TokenRefreshView, TokenRevokeView
from .token_throttles import (
    TokenRefreshFingerprintThrottle,
    TokenRefreshIPThrottle,
    TokenRefreshRateLimited,
    TokenRevokeFingerprintThrottle,
    TokenRevokeIPThrottle,
    TokenRevokeRateLimited,
)


class ThrottledTokenRefreshView(TokenRefreshView):
    throttle_classes = [TokenRefreshIPThrottle, TokenRefreshFingerprintThrottle]

    def throttled(self, request, wait):
        raise TokenRefreshRateLimited(wait=wait, request=request)


class ThrottledTokenRevokeView(TokenRevokeView):
    throttle_classes = [TokenRevokeIPThrottle, TokenRevokeFingerprintThrottle]

    def throttled(self, request, wait):
        raise TokenRevokeRateLimited(wait=wait, request=request)


urlpatterns = [
    path("register/", RegisterView.as_view(), name="register"),
    path("login/", LoginView.as_view(), name="login"),
    path("profile/", ProfileView.as_view(), name="profile"),
    path("users/me/", ProfileView.as_view(), name="users-me"),
    path("setup-password/", SessionRevokingSetupPasswordView.as_view(), name="setup-password"),
    path("forgot-password/", ForgotPasswordView.as_view(), name="forgot-password"),
    path("reset-password/", SessionRevokingResetPasswordView.as_view(), name="reset-password"),
    path("token/refresh/", ThrottledTokenRefreshView.as_view(), name="token-refresh"),
    path("token/revoke/", ThrottledTokenRevokeView.as_view(), name="token-revoke"),
    
    path("2fa/enable/", EnableTwoFactorView.as_view(), name="2fa-enable"),
    path("2fa/verify-setup/", VerifyTwoFactorSetupView.as_view(), name="2fa-verify-setup"),
    path("2fa/login/", LoginTwoFactorView.as_view(), name="2fa-login"),
    
    path("auth/google/", GoogleLoginView.as_view(), name="google-login"),
    path("auth/google/callback/", GoogleCallbackView.as_view(), name="google-callback"),
]
