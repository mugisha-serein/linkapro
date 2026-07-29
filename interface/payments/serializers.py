from rest_framework import serializers
from payments.domain.enums import PaymentMethod, PaymentEnv
from payments.domain.value_objects import Currency


class InitiatePaymentSerializer(serializers.Serializer):
    amount = serializers.DecimalField(max_digits=12, decimal_places=2)
    currency = serializers.ChoiceField(choices=["RWF", "USD", "EUR", "KES", "GHS", "NGN"])
    method = serializers.ChoiceField(choices=["card", "mobile_money", "bank_transfer"])
    idempotency_key = serializers.UUIDField()
    customer_email = serializers.EmailField()
    customer_name = serializers.CharField(max_length=200, required=False, allow_blank=True)
    context_reference = serializers.CharField(max_length=100, required=False, allow_blank=True)
    metadata = serializers.JSONField(required=False, default=dict)
    environment = serializers.ChoiceField(choices=["test", "live"], default="test")


class PaymentStatusSerializer(serializers.Serializer):
    reference = serializers.CharField()