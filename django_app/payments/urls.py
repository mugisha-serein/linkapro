from django.urls import path
from .views import InitiatePaymentView, PaymentPublicKeyView, PaymentStatusView, FlutterwaveWebhookView

app_name = "payments"

urlpatterns = [
    path("initiate/", InitiatePaymentView.as_view(), name="initiate"),
    path("status/<str:reference>/", PaymentStatusView.as_view(), name="status"),
    path("webhooks/flutterwave/", FlutterwaveWebhookView.as_view(), name="webhook"),
    path(".well-known/payment-public-key", PaymentPublicKeyView.as_view(), name="payment-public-key"),
]