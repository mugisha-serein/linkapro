from __future__ import annotations

from uuid import UUID
from typing import Iterable

from django.db.models import QuerySet

from apps.accounts.infrastructure.db.models import LoginActivity


class LoginActivityRepository:
    """Persistence-only access for LoginActivity records."""

    def create(self, **fields) -> LoginActivity:
        return LoginActivity.objects.create(**fields)

    def bulk_create(
        self,
        activities: Iterable[LoginActivity],
        batch_size: int = 1000,
    ) -> list[LoginActivity]:
        return LoginActivity.objects.bulk_create(
            activities,
            batch_size=batch_size,
        )

    def get_by_id(self, activity_id: UUID) -> LoginActivity | None:
        return LoginActivity.objects.filter(id=activity_id).first()

    def list_for_user(self, user_id: UUID) -> QuerySet[LoginActivity]:
        return LoginActivity.objects.filter(
            user_id=user_id
        ).order_by("-created_at")

    def list_for_session(self, session_id: UUID) -> QuerySet[LoginActivity]:
        return LoginActivity.objects.filter(
            session_id=session_id
        ).order_by("-created_at")

    def list_recent(self, limit: int = 100) -> QuerySet[LoginActivity]:
        safe_limit = min(limit, 1000)

        return LoginActivity.objects.filter().order_by("-created_at")[:safe_limit]

    def exists_for_user(self, user_id: UUID) -> bool:
        return LoginActivity.objects.filter(user_id=user_id).exists()

    def count_for_user(self, user_id: UUID) -> int:
        return LoginActivity.objects.filter(user_id=user_id).count()