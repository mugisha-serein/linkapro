from __future__ import annotations

from uuid import UUID
from django.db.models import QuerySet

from apps.accounts.infrastructure.db.models import RefreshToken


class TokenRepository:
    """Persistence-only access for RefreshToken records."""

    def create(self, **fields) -> RefreshToken:
        return RefreshToken.objects.create(**fields)

    # -------------------------
    # BASE QUERY
    # -------------------------
    def _base_queryset(self):
        return RefreshToken.objects.select_related("user", "session")

    # -------------------------
    # GETTERS
    # -------------------------
    def get_by_id(self, token_id: UUID) -> RefreshToken | None:
        return self._base_queryset().filter(id=token_id).first()

    def get_by_jti(self, jti: str) -> RefreshToken | None:
        return self._base_queryset().filter(jti=jti).first()

    def get_by_token_hash(self, token_hash: str) -> RefreshToken | None:
        return self._base_queryset().filter(token_hash=token_hash).first()

    # -------------------------
    # LISTING
    # -------------------------
    def list_by_user(self, user_id: UUID) -> QuerySet[RefreshToken]:
        return self._base_queryset().filter(user_id=user_id)

    def list_by_session(self, session_id: UUID) -> QuerySet[RefreshToken]:
        return self._base_queryset().filter(session_id=session_id)

    def list_by_family_id(self, family_id: UUID) -> QuerySet[RefreshToken]:
        return self._base_queryset().filter(family_id=family_id)

    def list_by_parent_jti(self, parent_jti: str) -> QuerySet[RefreshToken]:
        return self._base_queryset().filter(parent_jti=parent_jti)

    # -------------------------
    # STATE-AWARE QUERIES (IMPORTANT)
    # -------------------------
    def list_active_by_user(self, user_id: UUID) -> QuerySet[RefreshToken]:
        return self._base_queryset().filter(
            user_id=user_id,
            is_revoked=False,
        )

    def list_revoked_by_user(self, user_id: UUID) -> QuerySet[RefreshToken]:
        return self._base_queryset().filter(
            user_id=user_id,
            is_revoked=True,
        )

    # -------------------------
    # UPDATE / DELETE
    # -------------------------
    def update_by_id(self, token_id: UUID, **fields) -> int:
        return RefreshToken.objects.filter(id=token_id).update(**fields)

    def delete_by_id(self, token_id: UUID) -> int:
        deleted_count, _ = RefreshToken.objects.filter(id=token_id).delete()
        return deleted_count

    # -------------------------
    # SAFETY HELPERS
    # -------------------------
    def exists_by_jti(self, jti: str) -> bool:
        return RefreshToken.objects.filter(jti=jti).exists()

    def exists_active_by_session(self, session_id: UUID) -> bool:
        return RefreshToken.objects.filter(
            session_id=session_id,
            is_revoked=False,
        ).exists()