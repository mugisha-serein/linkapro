from django.urls import path
from .views import EnableTwoFactorView, LoginTwoFactorView, RegisterView,  VerifyTwoFactorSetupView

urlpatterns = [
    path("register/", RegisterView.as_view(), name="register"),
    path("2fa/enable/", EnableTwoFactorView.as_view(), name="2fa-enable"),
    path("2fa/verify-setup/", VerifyTwoFactorSetupView.as_view(), name="2fa-verify-setup"),
    path("2fa/login/", LoginTwoFactorView.as_view(), name="2fa-login"),
]