import json
import secrets
import uuid
from payments.application.ports import IAuditLogger, IKeyProvider
from payments.domain.entities import AuditEvent
from django_app.payments.models import AuditLog, Payment as DjangoPayment
from payments.domain.value_objects import EncryptedField
from payments.helpers.encryption import encrypted_field_to_json
from payments.infrastructure.crypto import encrypt_field


class DjangoAuditLogger(IAuditLogger):
    def __init__(self, key_provider: IKeyProvider):
        self.key_provider = key_provider

    def log(self, audit_event: AuditEvent) -> None:
        payment = None
        if audit_event.payment_id:
            try:
                payment = DjangoPayment.objects.get(id=audit_event.payment_id)
            except DjangoPayment.DoesNotExist:
                pass

        # Encrypt details
        dek = secrets.token_bytes(32)
        wrapped_dek = self.key_provider.wrap_dek(dek)
        plain_bytes = json.dumps(audit_event.details).encode('utf-8')
        ef = encrypt_field(plain_bytes, dek)
        ef_with_dek = EncryptedField(
            ciphertext=ef.ciphertext,
            iv=ef.iv,
            tag=ef.tag,
            dek_encrypted=wrapped_dek,
        )
        encrypted_details = encrypted_field_to_json(ef_with_dek)

        AuditLog.objects.create(
            id=audit_event.id,
            payment=payment,
            action=audit_event.action,
            actor=audit_event.actor,
            details=encrypted_details,
            dek_encrypted=wrapped_dek,
            created_at=audit_event.created_at,
        )