import json
import secrets
import uuid
import redis
import hashlib
import hmac
from django.conf import settings
from django.core.exceptions import ObjectDoesNotExist
from typing import Optional, List
from datetime import datetime, timedelta
from django.utils import timezone
from django.db.models import Sum

from payments.application.ports import IApiKeyRepository, IKeyProvider, IPaymentRepository, IWebhookEventRepository
from payments.domain.entities import Payment as DomainPayment, AuditEvent
from payments.domain.value_objects import EncryptedField, Money, Currency
from payments.domain.enums import PaymentStatus, PaymentMethod, PaymentEnv
from django_app.payments.models import Payment as DjangoPayment, WebhookEvent, AuditLog
from django_app.identity.models import User
from django_app.payments.models import ApiKey
from payments.domain.velocity import VelocityContext
from payments.helpers.encryption import encrypted_field_from_json, encrypted_field_to_json
from payments.infrastructure.crypto import decrypt_field, encrypt_field


class DjangoPaymentRepository(IPaymentRepository):
    def __init__(self, key_provider: IKeyProvider, redis_client: Optional[redis.Redis] = None):
        if key_provider is None:
            raise ValueError("key_provider is required")
        self.key_provider = key_provider
        self._redis_client = redis_client
        # Keep backward compatibility with environments where a dedicated
        # provider-reference HMAC key has not been configured yet.
        hmac_key = getattr(settings, "PROVIDER_REFERENCE_HMAC_KEY", None) or settings.SECRET_KEY
        self._hmac_key = hmac_key.encode()

    def _compute_provider_hash(self, provider_reference: str) -> str:
        if not provider_reference:
            return None
        digest = hmac.new(self._hmac_key, provider_reference.encode(), hashlib.sha256).hexdigest()
        return digest

    @property
    def redis_client(self):
        if self._redis_client is None:
            self._redis_client = redis.Redis.from_url(settings.REDIS_URL)
        return self._redis_client

    def acquire_lock(self, provider_reference: str, ttl_seconds: int = 30) -> bool:
        lock_key = f"payment_lock:{provider_reference}"
        return bool(self.redis_client.set(lock_key, "locked", nx=True, ex=ttl_seconds))

    def release_lock(self, provider_reference: str) -> None:
        lock_key = f"payment_lock:{provider_reference}"
        self.redis_client.delete(lock_key)

    def save(self, payment: DomainPayment) -> DomainPayment:
        dek = secrets.token_bytes(32)
        wrapped_dek = self.key_provider.wrap_dek(dek)

        encrypted_metadata = self._encrypt_json_field(payment.metadata, dek, wrapped_dek)

        # Persist to Django model
        django_payment, _ = DjangoPayment.objects.update_or_create(
            reference=payment.reference,
            defaults={
                "user_id": payment.user_id,
                "amount_minor": payment.amount.minor_units,
                "currency": payment.amount.currency.code,
                "method": payment.method.value,
                "idempotency_key": payment.idempotency_key,
                "environment": payment.environment.value,
                "status": payment.status.value,
                "provider_reference": payment.provider_reference,
                "provider_reference_hash": self._compute_provider_hash(payment.provider_reference),
                "context_reference": payment.context_reference,
                "metadata": encrypted_metadata,
                "created_at": payment.created_at,
                "expires_at": payment.expires_at,
                "dek_encrypted": wrapped_dek,
            },
        )

        django_payment.save()
        return self._to_domain(django_payment)

    def find_by_reference(self, reference: str) -> Optional[DomainPayment]:
        try:
            payment = DjangoPayment.objects.select_related("user").get(reference=reference)
            return self._to_domain(payment)
        except DjangoPayment.DoesNotExist:
            return None

    def find_by_provider_reference(self, provider_reference: str) -> Optional[DomainPayment]:
        if not provider_reference:
            return None
        hash_val = self._compute_provider_hash(provider_reference)
        try:
            payment = DjangoPayment.objects.select_related("user").get(provider_reference_hash=hash_val)
            return self._to_domain(payment)
        except DjangoPayment.DoesNotExist:
            return None

    def find_by_idempotency_key(self, idempotency_key: str) -> Optional[DomainPayment]:
        try:
            payment = DjangoPayment.objects.select_related("user").get(idempotency_key=idempotency_key)
            return self._to_domain(payment)
        except DjangoPayment.DoesNotExist:
            return None
        
    def get_velocity_context(self, user_id: uuid.UUID, now: datetime) -> VelocityContext:
        # Use database filtering for efficient aggregation
        one_hour_ago = now - timedelta(hours=1)
        one_day_ago = now - timedelta(days=1)

        # Payments in last hour
        payments_last_hour = DjangoPayment.objects.filter(
            user_id=user_id,
            created_at__gte=one_hour_ago
        ).count()

        # Payments in last day
        payments_last_day = DjangoPayment.objects.filter(
            user_id=user_id,
            created_at__gte=one_day_ago
        ).count()

        # Sum of amounts in last day (in minor units)
        amount_day = DjangoPayment.objects.filter(
            user_id=user_id,
            created_at__gte=one_day_ago
        ).aggregate(total=Sum('amount_minor'))['total'] or 0

        # Failed payments in last hour
        failed_last_hour = DjangoPayment.objects.filter(
            user_id=user_id,
            status=PaymentStatus.FAILED.value,
            created_at__gte=one_hour_ago
        ).count()

        # Unique vendors (via context_reference or provider_reference?)
        # For simplicity, we count distinct provider_references
        unique_vendors = DjangoPayment.objects.filter(
            user_id=user_id,
            created_at__gte=one_hour_ago,
            provider_reference__isnull=False
        ).values('provider_reference').distinct().count()

        # Account age – fetch user creation date
        from django_app.identity.models import User
        try:
            user = User.objects.get(id=user_id)
            account_age_hours = (now - user.created_at).total_seconds() / 3600
        except User.DoesNotExist:
            account_age_hours = 0

        return VelocityContext(
            payments_last_hour=payments_last_hour,
            payments_last_day=payments_last_day,
            amount_last_day_minor=int(amount_day),
            failed_last_hour=failed_last_hour,
            unique_vendors_last_hour=unique_vendors,
            account_age_hours=account_age_hours,
        )

    def find_duplicate_context_ref(self, user_id: uuid.UUID, context_ref: str, since: datetime) -> bool:
        if not context_ref:
            return False
        return DjangoPayment.objects.filter(
            user_id=user_id,
            context_reference=context_ref,
            created_at__gte=since
        ).exists()

    def _to_domain(self, model: DjangoPayment) -> DomainPayment:
        currency = Currency(model.currency)
        money = Money(minor_units=model.amount_minor, currency=currency)
        metadata = self._decrypt_json_field(model.metadata, model.dek_encrypted)
        return DomainPayment(
            id=model.id,
            user_id=model.user_id,
            amount=money,
            method=PaymentMethod(model.method),
            reference=model.reference,
            idempotency_key=model.idempotency_key,
            environment=PaymentEnv(model.environment),
            status=PaymentStatus(model.status),
            provider_reference=model.provider_reference,
            context_reference=model.context_reference,
            metadata=metadata,
            created_at=model.created_at,
            expires_at=model.expires_at,
        )

    def _encrypt_json_field(self, value: dict, dek: bytes, wrapped_dek: bytes) -> dict:
        plain_bytes = json.dumps(value or {}).encode("utf-8")
        ef = encrypt_field(plain_bytes, dek)
        encrypted = EncryptedField(
            ciphertext=ef.ciphertext,
            iv=ef.iv,
            tag=ef.tag,
            dek_encrypted=wrapped_dek,
        )
        return encrypted_field_to_json(encrypted)

    def _decrypt_json_field(self, value, wrapped_dek: Optional[bytes]) -> dict:
        if not value:
            return {}
        if not wrapped_dek:
            return value if isinstance(value, dict) else {}
        if isinstance(value, dict) and {"ciphertext", "iv", "tag", "dek_encrypted"}.issubset(value.keys()):
            ef = encrypted_field_from_json(value)
            dek = self.key_provider.unwrap_dek(wrapped_dek)
            plain_bytes = decrypt_field(ef, dek)
            return json.loads(plain_bytes.decode("utf-8"))
        return value if isinstance(value, dict) else {}


class DjangoWebhookEventRepository(IWebhookEventRepository):
    def __init__(self, key_provider: IKeyProvider):
        if key_provider is None:
            raise ValueError("key_provider is required")
        self.key_provider = key_provider

    def exists(self, event_id: str) -> bool:
        return WebhookEvent.objects.filter(event_id=event_id).exists()

    def save_event(self, event_id: str, status: str, payload: dict) -> None:
        dek = secrets.token_bytes(32)
        wrapped_dek = self.key_provider.wrap_dek(dek)
        plain_bytes = json.dumps(payload).encode('utf-8')
        ef = encrypt_field(plain_bytes, dek)
        # Build complete EncryptedField with wrapped DEK
        ef_with_dek = EncryptedField(
            ciphertext=ef.ciphertext,
            iv=ef.iv,
            tag=ef.tag,
            dek_encrypted=wrapped_dek,
        )
        encrypted_payload = encrypted_field_to_json(ef_with_dek)

        WebhookEvent.objects.update_or_create(
            event_id=event_id,
            defaults={
                "status": status,
                "payload": encrypted_payload,
                "dek_encrypted": wrapped_dek,
            },
        )

class DjangoApiKeyRepository(IApiKeyRepository):
    def find_by_key_id(self, key_id: str) -> Optional[dict]:
        try:
            key = ApiKey.objects.get(key_id=key_id)
            if not key.is_active:
                return None
            if key.expires_at and key.expires_at < timezone.now():
                return None
            if not key.secret_plain:
                return None
            return {
                "key_id": key.key_id,
                "secret": key.secret_plain,
                "scopes": key.scopes,
                "user_id": key.user_id,
                "is_active": key.is_active,
                "expires_at": key.expires_at,
            }
        except ApiKey.DoesNotExist:
            return None

    def mark_used(self, key_id: str) -> None:
        ApiKey.objects.filter(key_id=key_id).update(last_used_at=timezone.now())
