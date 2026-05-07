"""Repository interfaces (ABCs) for identity."""
from abc import ABC, abstractmethod
from typing import Optional, List
import uuid

from .entities import User, OAuthToken
from .value_objects import Email, OAuthProvider


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
    def delete(self, user_id: uuid.UUID) -> None:
        """Permanently delete user (use with caution)."""

    @abstractmethod
    def set_totp_secret(self, user_id: uuid.UUID, secret: str) -> None: ...
    
    @abstractmethod
    def get_totp_secret(self, user_id: uuid.UUID) -> Optional[str]: ...


class IOAuthTokenRepository(ABC):
    @abstractmethod
    def get_by_provider_and_user(
        self, provider: OAuthProvider, provider_user_id: str
    ) -> Optional[OAuthToken]:
        """Retrieve token by provider and external user ID."""

    @abstractmethod
    def save(self, token: OAuthToken) -> OAuthToken:
        """Save OAuth token."""

    @abstractmethod
    def get_by_user_and_provider(
        self, user_id: uuid.UUID, provider: OAuthProvider
    ) -> Optional[OAuthToken]:
        """Retrieve token by internal user and provider."""

    @abstractmethod
    def delete_for_user(self, user_id: uuid.UUID, provider: OAuthProvider) -> None:
        """Remove linked provider for user."""
