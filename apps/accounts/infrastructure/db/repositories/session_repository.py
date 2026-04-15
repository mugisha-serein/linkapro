from __future__ import annotations

from uuid import UUID
from django.db.models import QuerySet

from apps.accounts.infrastructure.db.models import UserSession


class SessionRepository:
    """Persistence-only access for UserSession records."""

    def create(self, **fields) -> UserSession:
        return UserSession.objects.create(**fields)

    # -------------------------
    # BASE QUERY
    # -------------------------
    def _base_queryset(self):
        return UserSession.objects.select_related("user", "device")

    # -------------------------
    # GETTERS
    # -------------------------
    def get_by_id(self, session_id: UUID) -> UserSession | None:
        return self._base_queryset().filter(id=session_id).first()

    def get_by_session_key(self, session_key: str) -> UserSession | None:
        return self._base_queryset().filter(session_key=session_key).first()

    def get_by_refresh_token_jti(self, refresh_token_jti: str) -> UserSession | None:
        return self._base_queryset().filter(
            refresh_token_jti=refresh_token_jti
        ).first()

    # -------------------------
    # LISTING
    # -------------------------
    def list_by_user(self, user_id: UUID) -> QuerySet[UserSession]:
        return self._base_queryset().filter(user_id=user_id)

    def list_by_device(self, device_id: UUID) -> QuerySet[UserSession]:
        return self._base_queryset().filter(device_id=device_id)

    def list_by_user_and_device(
        self,
        user_id: UUID,
        device_id: UUID,
    ) -> QuerySet[UserSession]:
        return self._base_queryset().filter(
            user_id=user_id,
            device_id=device_id,
        )

    def list_active_by_user(self, user_id: UUID) -> QuerySet[UserSession]:
        return self._base_queryset().filter(
            user_id=user_id,
            is_active=True,
        )

    # -------------------------
    # UPDATE / DELETE
    # -------------------------
    def update_by_id(self, session_id: UUID, **fields) -> int:
        return UserSession.objects.filter(id=session_id).update(**fields)

    def delete_by_id(self, session_id: UUID) -> int:
        deleted_count, _ = UserSession.objects.filter(id=session_id).delete()
        return deleted_count

    # -------------------------
    # SAFETY HELPERS
    # -------------------------
    def exists_by_refresh_token_jti(self, jti: str) -> bool:
        return UserSession.objects.filter(refresh_token_jti=jti).exists()

    def exists_active_session(self, user_id: UUID) -> bool:
        return UserSession.objects.filter(
            user_id=user_id,
            is_active=True,
        ).exists()