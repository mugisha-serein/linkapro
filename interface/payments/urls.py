from django.urls import path
from .views import (
    FlutterwaveWebhookView,
    InitiatePaymentView,
    PaymentListView,
    PaymentPublicKeyView,
    PaymentStatusView,
    PaymentSummaryView,
)

app_name = "payments"

urlpatterns = [
    path("", PaymentListView.as_view(), name="list"),
    path("initiate/", InitiatePaymentView.as_view(), name="initiate"),
    path("summary/", PaymentSummaryView.as_view(), name="summary"),
    path("status/<str:reference>/", PaymentStatusView.as_view(), name="status"),
    path("webhooks/flutterwave/", FlutterwaveWebhookView.as_view(), name="webhook"),
    path(".well-known/payment-public-key", PaymentPublicKeyView.as_view(), name="payment-public-key"),
]
