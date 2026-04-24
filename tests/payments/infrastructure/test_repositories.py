import json
import secrets
from typing import Optional
from django.core.exceptions import ObjectDoesNotExist
from django.db import transaction
import redis
from django.conf import settings

from payments.application.ports import IPaymentRepository, IKeyProvider
from payments.domain.entities import Payment as DomainPayment, AuditEvent
from payments.domain.value_objects import Money, Currency, EncryptedField
from payments.domain.enums import PaymentStatus, PaymentMethod, PaymentEnv
from django_app.payments.models import Payment as DjangoPayment, WebhookEvent, AuditLog
from django_app.identity.models import User
from payments.infrastructure.crypto import encrypt_field, decrypt_field
from payments.helpers.encryption import encrypted_field_to_json, encrypted_field_from_json


class DjangoPaymentRepository(IPaymentRepository):
    def __init__(self, key_provider: IKeyProvider):
        self.key_provider = key_provider
        self._redis_client = None

    @property
    def redis_client(self):
        if self._redis_client is None:
            self._redis_client = redis.Redis.from_url(settings.REDIS_URL)
        return self._redis_client

    def save(self, payment: DomainPayment) -> DomainPayment:
        # Generate DEK
        dek = secrets.token_bytes(32)
        wrapped_dek = self.key_provider.wrap_dek(dek)

        # Encrypt fields and replace in domain entity
        if payment.metadata:
            plain_bytes = json.dumps(payment.metadata).encode('utf-8')
            ef = encrypt_field(plain_bytes, dek)
            ef = EncryptedField(
                ciphertext=ef.ciphertext,
                iv=ef.iv,
                tag=ef.tag,
                dek_encrypted=wrapped_dek,
            )
            payment.metadata = encrypted_field_to_json(ef)

        if payment.provider_reference:
            plain_bytes = payment.provider_reference.encode('utf-8')
            ef = encrypt_field(plain_bytes, dek)
            ef = EncryptedField(
                ciphertext=ef.ciphertext,
                iv=ef.iv,
                tag=ef.tag,
                dek_encrypted=wrapped_dek,
            )
            payment.provider_reference = json.dumps(encrypted_field_to_json(ef))

        if payment.context_reference:
            plain_bytes = payment.context_reference.encode('utf-8')
            ef = encrypt_field(plain_bytes, dek)
            ef = EncryptedField(
                ciphertext=ef.ciphertext,
                iv=ef.iv,
                tag=ef.tag,
                dek_encrypted=wrapped_dek,
            )
            payment.context_reference = json.dumps(encrypted_field_to_json(ef))

        # Persist to Django model
        try:
            django_payment = DjangoPayment.objects.get(id=payment.id)
        except DjangoPayment.DoesNotExist:
            django_payment = DjangoPayment(id=payment.id)

        django_payment.user = User.objects.get(id=payment.user_id)
        django_payment.amount_minor = payment.amount.minor_units
        django_payment.currency = payment.amount.currency.code
        django_payment.method = payment.method.value
        django_payment.status = payment.status.value
        django_payment.reference = payment.reference
        django_payment.idempotency_key = payment.idempotency_key
        django_payment.provider_reference = payment.provider_reference  # now encrypted JSON string
        django_payment.context_reference = payment.context_reference    # encrypted JSON string
        django_payment.metadata = payment.metadata                      # encrypted JSON dict
        django_payment.environment = payment.environment.value
        django_payment.expires_at = payment.expires_at
        django_payment.dek_encrypted = wrapped_dek
        django_payment.save()

        return self._to_domain(django_payment)

    def _to_domain(self, model: DjangoPayment) -> DomainPayment:
        # Unwrap DEK
        wrapped_dek = model.dek_encrypted
        if wrapped_dek is None:
            # Handle unencrypted legacy rows (if any)
            dek = None
        else:
            dek = self.key_provider.unwrap_dek(wrapped_dek)

        # Decrypt fields
        metadata = model.metadata
        if dek and metadata:
            ef = encrypted_field_from_json(metadata)
            plain_bytes = decrypt_field(ef, dek)
            metadata = json.loads(plain_bytes.decode('utf-8'))

        provider_reference = model.provider_reference
        if dek and provider_reference:
            ef = encrypted_field_from_json(json.loads(provider_reference))
            plain_bytes = decrypt_field(ef, dek)
            provider_reference = plain_bytes.decode('utf-8')

        context_reference = model.context_reference
        if dek and context_reference:
            ef = encrypted_field_from_json(json.loads(context_reference))
            plain_bytes = decrypt_field(ef, dek)
            context_reference = plain_bytes.decode('utf-8')

        currency = Currency(model.currency)
        money = Money(minor_units=model.amount_minor, currency=currency)

        return DomainPayment(
            id=model.id,
            user_id=model.user_id,
            amount=money,
            method=PaymentMethod(model.method),
            reference=model.reference,
            idempotency_key=model.idempotency_key,
            environment=PaymentEnv(model.environment),
            status=PaymentStatus(model.status),
            provider_reference=provider_reference,
            context_reference=context_reference,
            metadata=metadata or {},
            created_at=model.created_at,
            expires_at=model.expires_at,
        )