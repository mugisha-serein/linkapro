"""User account persistence port."""

from abc import ABC, abstractmethod
from typing import Optional
import uuid

from domain.identity.account import User
from domain.identity.credentials import Email, PasswordHistory


class IUserRepository(ABC):
    @abstractmethod
    def get_by_id(self, user_id: uuid.UUID) -> Optional[User]:
        """Retrieve user by ID."""

    @abstractmethod
    def get_by_email(self, email: Email) -> Optional[User]:
        """Retrieve user by email."""

    @abstractmethod
    def save(self, user: User) -> User:
        """Persist new or updated user."""

    @abstractmethod
    def get_password_history(self, user_id: uuid.UUID) -> PasswordHistory:
        """Retrieve recent password hashes for reuse prevention."""

    @abstractmethod
    def delete(self, user_id: uuid.UUID) -> None:
        """
        Permanently delete user data.

        Dangerous: do not use for normal account removal. Prefer deactivate(),
        or a scheduled deletion/anonymization workflow with an explicit policy.
        """

    @abstractmethod
    def deactivate(self, user_id: uuid.UUID) -> None:
        """Deactivate a user without permanently deleting data."""


__all__ = ["IUserRepository"]
