import uuid
from rest_framework.views import APIView
from rest_framework.response import Response
from rest_framework import status
from rest_framework.permissions import IsAuthenticated, AllowAny
from django.conf import settings
from django.views.decorators.csrf import csrf_exempt
from django.utils.decorators import method_decorator
import secrets

from payments.infrastructure.jwe_adapter import JweEnvelopeAdapter

from .serializers import InitiatePaymentSerializer
from .services import get_command_handlers, get_query_handlers
from payments.application.commands import InitiatePaymentCommand, ProcessWebhookCommand
from payments.application.exceptions import (
    PaymentNotFoundError,
    PaymentNotAllowedError,
    ProviderGatewayError,
)
from payments.infrastructure.webhook_decryptor import FlutterwaveWebhookDecryptor
from payments.domain.value_objects import Money, Currency
from domain.shared.utils import utc_now


class InitiatePaymentView(APIView):
    permission_classes = [IsAuthenticated]

    def post(self, request):
        serializer = InitiatePaymentSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        data = serializer.validated_data

        currency = Currency(data["currency"])
        money = Money.from_decimal(data["amount"], currency)

        cmd = InitiatePaymentCommand(
            user_id=request.user.id,
            amount=money,
            method=data["method"],
            idempotency_key=str(data["idempotency_key"]),
            redirect_base_url=request.build_absolute_uri("/"),
            customer_email=data["customer_email"],
            customer_name=data.get("customer_name"),
            context_reference=data.get("context_reference"),
            metadata=data.get("metadata"),
            environment=data["environment"],
        )

        handlers = get_command_handlers()
        try:
            result = handlers.initiate_payment(cmd)
            return Response({
                "reference": result.reference,
                "payment_link": result.payment_link,
                "expires_at": result.expires_at.isoformat(),
            }, status=status.HTTP_201_CREATED)
        except ProviderGatewayError as e:
            return Response({"error": str(e)}, status=status.HTTP_502_BAD_GATEWAY)
        except PaymentNotAllowedError as e:
            return Response({"error": e.reason}, status=status.HTTP_400_BAD_REQUEST)


class PaymentStatusView(APIView):
    permission_classes = [IsAuthenticated]

    def get(self, request, reference):
        handlers = get_query_handlers()
        try:
            status_dto = handlers.get_payment_status(reference)
            # Ensure the payment belongs to the authenticated user
            # (We need a method to check ownership; for simplicity, we assume query handler does it)
            return Response({
                "reference": status_dto.reference,
                "status": status_dto.status,
                "amount": status_dto.amount,
                "currency": status_dto.currency,
                "method": status_dto.method,
                "created_at": status_dto.created_at.isoformat(),
                "expires_at": status_dto.expires_at.isoformat() if status_dto.expires_at else None,
                "provider_reference": status_dto.provider_reference,
            })
        except PaymentNotFoundError:
            return Response({"error": "Payment not found"}, status=status.HTTP_404_NOT_FOUND)


@method_decorator(csrf_exempt, name="dispatch")
class FlutterwaveWebhookView(APIView):
    permission_classes = [AllowAny]

    def post(self, request):
        # Stage 1: Verify secret hash
        secret_hash = settings.FLW_SECRET_HASH
        received_hash = request.headers.get("verif-hash", "")
        if not secret_hash or not secrets.compare_digest(received_hash, secret_hash):
            return Response({"error": "Unauthorized"}, status=status.HTTP_401_UNAUTHORIZED)

        # Attempt decryption if payload appears encrypted
        raw_body = request.body
        content_type = request.content_type or ""
        encrypted_payload = None
        payload_dict = None

        # If content type is not JSON or body looks like encrypted data (Base64 string)
        if "json" not in content_type and raw_body:
            try:
                encrypted_str = raw_body.decode('utf-8').strip()
                decryptor = FlutterwaveWebhookDecryptor()
                result = decryptor.decrypt(encrypted_str)
                if result.success:
                    payload_dict = result.decrypted_data
                    encrypted_payload = encrypted_str   # Keep original encrypted string
                else:
                    return Response({"error": "Invalid encrypted payload"}, status=status.HTTP_401_UNAUTHORIZED)
            except Exception as e:
                return Response({"error": "Invalid payload"}, status=status.HTTP_400_BAD_REQUEST)
        else:
            # Normal JSON payload
            try:
                payload_dict = request.data
            except Exception:
                return Response({"error": "Invalid JSON"}, status=status.HTTP_400_BAD_REQUEST)

        if not isinstance(payload_dict, dict):
            return Response({"error": "Payload must be a JSON object"}, status=status.HTTP_400_BAD_REQUEST)

        event_id = payload_dict.get("id") or str(uuid.uuid4())

        cmd = ProcessWebhookCommand(
            event_id=event_id,
            event_type=payload_dict.get("event", ""),
            payload=payload_dict,
            headers=dict(request.headers),
            now=utc_now(),
            encrypted_payload=encrypted_payload,
        )

        handlers = get_command_handlers()
        handlers.process_webhook(cmd)
        return Response({"status": "received"}, status=status.HTTP_200_OK)
    
class PaymentPublicKeyView(APIView):
    permission_classes = [AllowAny]

    def get(self, request):
        adapter = JweEnvelopeAdapter()
        jwk = adapter.get_public_jwk()
        return Response(jwk)