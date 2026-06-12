import uuid
from decimal import Decimal
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
from .models import Payment as DjangoPayment


PAYMENT_DECIMALS = {"RWF": 0, "USD": 2, "EUR": 2, "KES": 2, "GHS": 2, "NGN": 2}


def _payment_amount(payment: DjangoPayment) -> str:
    decimals = PAYMENT_DECIMALS.get(payment.currency, 2)
    divisor = Decimal(10) ** decimals
    return str(Decimal(payment.amount_minor) / divisor)


def _serialize_payment(payment: DjangoPayment) -> dict:
    return {
        "reference": payment.reference,
        "status": payment.status,
        "amount": _payment_amount(payment),
        "currency": payment.currency,
        "method": payment.method,
        "created_at": payment.created_at.isoformat(),
        "expires_at": payment.expires_at.isoformat() if payment.expires_at else None,
        "provider_reference": payment.provider_reference,
    }


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
            allow_global_lookup = bool(
                getattr(request.user, "is_staff", False)
                or getattr(request.user, "role", None) == "admin"
            )
            status_dto = handlers.get_payment_status(
                reference,
                user_id=request.user.id,
                allow_global_lookup=allow_global_lookup,
            )
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


class PaymentListView(APIView):
    permission_classes = [IsAuthenticated]

    def get(self, request):
        payments = DjangoPayment.objects.filter(user=request.user).order_by("-created_at")
        requested_status = request.query_params.get("status")
        if requested_status:
            payments = payments.filter(status=requested_status)

        try:
            page = max(int(request.query_params.get("page", 1)), 1)
        except ValueError:
            page = 1
        page_size = 20
        start = (page - 1) * page_size
        end = start + page_size

        return Response({
            "results": [_serialize_payment(payment) for payment in payments[start:end]],
            "count": payments.count(),
        })


class PaymentSummaryView(APIView):
    permission_classes = [IsAuthenticated]

    def get(self, request):
        payments = DjangoPayment.objects.filter(user=request.user)
        successful = payments.filter(status=DjangoPayment.Status.SUCCESS)
        pending = payments.filter(status=DjangoPayment.Status.PENDING)
        failed = payments.filter(status=DjangoPayment.Status.FAILED)

        total_paid = Decimal("0")
        for payment in successful:
            total_paid += Decimal(_payment_amount(payment))

        pending_amount = Decimal("0")
        for payment in pending:
            pending_amount += Decimal(_payment_amount(payment))

        return Response({
            "total_payments": payments.count(),
            "successful_payments": successful.count(),
            "pending_payments": pending.count(),
            "failed_payments": failed.count(),
            "total_paid": str(total_paid),
            "pending_amount": str(pending_amount),
            "transaction_count": payments.count(),
        })


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
