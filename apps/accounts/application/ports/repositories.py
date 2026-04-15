# No Business Logic Here
from __future__ import annotations

from typing import Protocol, Any
from uuid import UUID
from django.db.models import QuerySet


class UserRepository(Protocol):
    def create(self, **fields) -> Any:
        ...

    def get_by_id(self, user_id: UUID) -> Any | None:
        ...

    def get_by_email(self, email: str) -> Any | None:
        ...

    def save(self, user: Any, update_fields: list[str] | None = None) -> None:
        ...


class DeviceRepository(Protocol):
    def create(self, **fields) -> Any:
        ...

    def get_by_id(self, device_id: UUID) -> Any | None:
        ...

    def get_by_user_and_fingerprint_hash(self, user_id: UUID, fingerprint_hash: str) -> Any | None:
        ...

    def update_by_id(self, device_id: UUID, **fields) -> int:
        ...


class SessionRepository(Protocol):
    def create(self, **fields) -> Any:
        ...

    def get_by_id(self, session_id: UUID) -> Any | None:
        ...

    def get_by_session_key(self, session_key: str) -> Any | None:
        ...

    def update_by_id(self, session_id: UUID, **fields) -> int:
        ...

    def list_by_user(self, user_id: UUID) -> QuerySet:
        ...


class TokenRepository(Protocol):
    def create(self, **fields) -> Any:
        ...

    def get_by_id(self, token_id: UUID) -> Any | None:
        ...

    def get_by_jti(self, jti: str) -> Any | None:
        ...

    def get_by_token_hash(self, token_hash: str) -> Any | None:
        ...

    def update_by_id(self, token_id: UUID, **fields) -> int:
        ...

    def list_by_session(self, session_id: UUID) -> QuerySet:
        ...


class LoginActivityRepository(Protocol):
    def create(self, **fields) -> Any:
        ...

    def list_for_user(self, user_id: UUID) -> QuerySet:
        ...