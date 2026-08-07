from django.urls import path
from .views.auth import LoginView, ProfileView, RegisterView
from .views.account_admin import (
    AssignRoleView,
    ReactivateAccountView,
    SuspendAccountView,
    UnlockAccountView,
)
from .views.mfa import (
    EnableTwoFactorView,
    GoogleCallbackView,
    GoogleLoginView,
    LoginTwoFactorView,
    VerifyTwoFactorSetupView,
)
from .views.password import (
    ForgotPasswordView,
    ResetPasswordView,
    SessionRevokingSetupPasswordView,
)
from .views.session import (
    ActiveSessionsView,
    RevokeNamedSessionView,
    RevokeOtherSessionsView,
    TokenRefreshView,
    TokenRevokeView,
)
from .views.security import (
    ChangePasswordView,
    DisableMfaView,
    GenerateRecoveryCodesView,
    RegenerateRecoveryCodesView,
)
from .views.verification import RequestEmailVerificationView, ResendEmailVerificationView
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
    # No-trailing-slash aliases for POST endpoints so clients that hit them
    # without a trailing slash do not trigger Django's APPEND_SLASH redirect
    # (which cannot preserve a POST body and raises a RuntimeError / 500).
    path("register", RegisterView.as_view(), name="register-no-slash"),
    path("login", LoginView.as_view(), name="login-no-slash"),
    path("refresh", ThrottledTokenRefreshView.as_view(), name="refresh-no-slash"),
    path("revoke", ThrottledTokenRevokeView.as_view(), name="revoke-no-slash"),

    path("register/", RegisterView.as_view(), name="register"),
    path("login/", LoginView.as_view(), name="login"),
    path("profile/", ProfileView.as_view(), name="profile"),
    path("users/me/", ProfileView.as_view(), name="users-me"),
    path("users/<uuid:user_id>/assign-role/", AssignRoleView.as_view(), name="assign-role"),
    path("users/<uuid:user_id>/suspend/", SuspendAccountView.as_view(), name="suspend-account"),
    path("users/<uuid:user_id>/reactivate/", ReactivateAccountView.as_view(), name="reactivate-account"),
    path("users/<uuid:user_id>/unlock/", UnlockAccountView.as_view(), name="unlock-account"),
    path("change-password/", ChangePasswordView.as_view(), name="change-password"),
    path("setup-password/", SessionRevokingSetupPasswordView.as_view(), name="setup-password"),
    path("forgot-password/", ForgotPasswordView.as_view(), name="forgot-password"),
    path("reset-password/", ResetPasswordView.as_view(), name="reset-password"),
    path("email-verification/request/", RequestEmailVerificationView.as_view(), name="request-email-verification"),
    path(
        "email-verification/<uuid:challenge_id>/resend/",
        ResendEmailVerificationView.as_view(),
        name="resend-email-verification",
    ),
    path("refresh/", ThrottledTokenRefreshView.as_view(), name="refresh"),
    path("revoke/", ThrottledTokenRevokeView.as_view(), name="revoke"),
    path("token/refresh/", ThrottledTokenRefreshView.as_view(), name="token-refresh"),
    path("token/revoke/", ThrottledTokenRevokeView.as_view(), name="token-revoke"),
    path("sessions/", ActiveSessionsView.as_view(), name="active-sessions"),
    path("sessions/<uuid:session_id>/revoke/", RevokeNamedSessionView.as_view(), name="revoke-named-session"),
    path("sessions/revoke-other/", RevokeOtherSessionsView.as_view(), name="revoke-other-sessions"),
    
    path("2fa/enable/", EnableTwoFactorView.as_view(), name="2fa-enable"),
    path("2fa/verify-setup/", VerifyTwoFactorSetupView.as_view(), name="2fa-verify-setup"),
    path("2fa/login/", LoginTwoFactorView.as_view(), name="2fa-login"),
    path("2fa/disable/", DisableMfaView.as_view(), name="2fa-disable"),
    path("2fa/recovery-codes/", GenerateRecoveryCodesView.as_view(), name="2fa-recovery-codes"),
    path("2fa/recovery-codes/regenerate/", RegenerateRecoveryCodesView.as_view(), name="2fa-recovery-codes-regenerate"),
    
    path("auth/google/", GoogleLoginView.as_view(), name="google-login"),
    path("auth/google/callback/", GoogleCallbackView.as_view(), name="google-callback"),
]
