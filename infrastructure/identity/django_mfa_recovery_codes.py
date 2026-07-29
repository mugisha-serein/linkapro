"""Django-backed MFA recovery-code adapters."""

import hashlib
import hmac
import secrets
import uuid
from datetime import datetime

from django.conf import settings
from django.core.cache import cache
from django.core.exceptions import ImproperlyConfigured

from application.identity.shared.ports import (
    MfaRecoveryCodeRepository,
    RecoveryCodeGenerator,
    RecoveryCodeHasher,
)
from domain.identity.mfa import RecoveryCode


def _recovery_codes_key(user_id: uuid.UUID) -> str:
    return f"mfa-recovery-codes:{user_id}"


def _hash_key() -> bytes:
    key = str(getattr(settings, "MFA_RECOVERY_CODE_HASH_KEY", "") or "").strip()
    if not key:
        raise ImproperlyConfigured("MFA_RECOVERY_CODE_HASH_KEY must be set")
    return key.encode("utf-8")


def _serialize_recovery_codes(recovery_codes: tuple[RecoveryCode, ...]) -> list[dict]:
    return [
        {
            "id": str(recovery_code.id),
            "code_hash": recovery_code.code_hash,
            "used_at": recovery_code.used_at.isoformat() if recovery_code.used_at else None,
        }
        for recovery_code in recovery_codes
    ]


def _deserialize_recovery_codes(value) -> tuple[RecoveryCode, ...]:
    if not isinstance(value, list):
        return ()
    recovery_codes = []
    for item in value:
        if not isinstance(item, dict):
            return ()
        try:
            recovery_codes.append(
                RecoveryCode(
                    id=uuid.UUID(str(item["id"])),
                    code_hash=str(item["code_hash"]),
                    used_at=(
                        datetime.fromisoformat(str(item["used_at"]))
                        if item.get("used_at")
                        else None
                    ),
                )
            )
        except (KeyError, TypeError, ValueError):
            return ()
    return tuple(recovery_codes)


class DjangoMfaRecoveryCodeRepository(MfaRecoveryCodeRepository):
    def get_for_user(self, user_id: uuid.UUID) -> tuple[RecoveryCode, ...]:
        return _deserialize_recovery_codes(cache.get(_recovery_codes_key(user_id)))

    def save_for_user(self, user_id: uuid.UUID, recovery_codes: tuple[RecoveryCode, ...]) -> None:
        cache.set(_recovery_codes_key(user_id), _serialize_recovery_codes(recovery_codes), timeout=None)

    def replace_for_user(self, user_id: uuid.UUID, recovery_codes: tuple[RecoveryCode, ...]) -> None:
        self.save_for_user(user_id, recovery_codes)

    def clear_for_user(self, user_id: uuid.UUID) -> None:
        cache.delete(_recovery_codes_key(user_id))


class HmacRecoveryCodeHasher(RecoveryCodeHasher):
    def hash_recovery_code(self, code: str) -> str:
        return hmac.new(_hash_key(), code.encode("utf-8"), hashlib.sha256).hexdigest()


class SecureRecoveryCodeGenerator(RecoveryCodeGenerator):
    def generate(self) -> str:
        return f"{secrets.token_hex(4)}-{secrets.token_hex(4)}"


__all__ = [
    "DjangoMfaRecoveryCodeRepository",
    "HmacRecoveryCodeHasher",
    "SecureRecoveryCodeGenerator",
]
