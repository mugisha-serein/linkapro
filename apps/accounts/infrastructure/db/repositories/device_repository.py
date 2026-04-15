from __future__ import annotations

from uuid import UUID
from django.db.models import QuerySet

from apps.accounts.infrastructure.db.models import DeviceFingerprint


class DeviceRepository:
    """Persistence-only access for DeviceFingerprint records."""

    def create(self, **fields) -> DeviceFingerprint:
        return DeviceFingerprint.objects.create(**fields)

    def get_by_id(self, device_id: UUID) -> DeviceFingerprint | None:
        return DeviceFingerprint.objects.filter(id=device_id).first()

    def get_by_user_and_fingerprint_hash(
        self,
        user_id: UUID,
        fingerprint_hash: str,
    ) -> DeviceFingerprint | None:
        return DeviceFingerprint.objects.filter(
            user_id=user_id,
            fingerprint_hash=fingerprint_hash,
        ).first()

    def list_by_user(self, user_id: UUID) -> QuerySet[DeviceFingerprint]:
        return DeviceFingerprint.objects.filter(user_id=user_id)

    def list_by_fingerprint_hash(self, fingerprint_hash: str) -> QuerySet[DeviceFingerprint]:
        return DeviceFingerprint.objects.filter(fingerprint_hash=fingerprint_hash)

    def exists_by_user_and_fingerprint_hash(
        self,
        user_id: UUID,
        fingerprint_hash: str,
    ) -> bool:
        return DeviceFingerprint.objects.filter(
            user_id=user_id,
            fingerprint_hash=fingerprint_hash,
        ).exists()

    def update_by_id(self, device_id: UUID, **fields) -> int:
        return DeviceFingerprint.objects.filter(id=device_id).update(**fields)

    def delete_by_id(self, device_id: UUID) -> int:
        deleted_count, _ = DeviceFingerprint.objects.filter(id=device_id).delete()
        return deleted_count