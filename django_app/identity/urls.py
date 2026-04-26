from django.urls import path
from .views import (
    RegisterView,
    LoginView,
    EnableTwoFactorView,
    VerifyTwoFactorSetupView,
    LoginTwoFactorView,
)

urlpatterns = [
    path("register/", RegisterView.as_view(), name="register"),
    path("login/", LoginView.as_view(), name="login"),
    path("2fa/enable/", EnableTwoFactorView.as_view(), name="2fa-enable"),
    path("2fa/verify-setup/", VerifyTwoFactorSetupView.as_view(), name="2fa-verify-setup"),
    path("2fa/login/", LoginTwoFactorView.as_view(), name="2fa-login"),
]