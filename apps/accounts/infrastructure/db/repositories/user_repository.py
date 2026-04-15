from __future__ import annotations

from uuid import UUID
from django.db.models import QuerySet

from apps.accounts.infrastructure.db.models import User


class UserRepository:
    """Persistence-only access for User records."""

    # -------------------------
    # BASE QUERY
    # -------------------------
    def _base_queryset(self):
        return User.objects.all()

    # -------------------------
    # CREATE (IMPORTANT FIX)
    # -------------------------
    def create(self, **fields) -> User:
        """
        WARNING:
        This assumes fields are already validated and processed
        by application layer (especially password handling).
        """
        return User.objects.create(**fields)

    # -------------------------
    # GETTERS
    # -------------------------
    def get_by_id(self, user_id: UUID) -> User | None:
        return self._base_queryset().filter(id=user_id).first()

    def get_by_email(self, email: str) -> User | None:
        return self._base_queryset().filter(email=email).first()

    def get_active_by_email(self, email: str) -> User | None:
        return self._base_queryset().filter(
            email=email,
            is_active=True,
        ).first()

    # -------------------------
    # EXISTS
    # -------------------------
    def exists_by_email(self, email: str) -> bool:
        return self._base_queryset().filter(email=email).exists()

    def exists_by_id(self, user_id: UUID) -> bool:
        return self._base_queryset().filter(id=user_id).exists()

    # -------------------------
    # LISTING
    # -------------------------
    def list_by_ids(self, user_ids: list[UUID]) -> QuerySet[User]:
        return self._base_queryset().filter(id__in=user_ids)

    # -------------------------
    # UPDATE / SAVE
    # -------------------------
    def save(self, user: User, update_fields: list[str] | None = None) -> User:
        user.save(update_fields=update_fields)
        return user

    def update_by_id(self, user_id: UUID, **fields) -> int:
        return self._base_queryset().filter(id=user_id).update(**fields)