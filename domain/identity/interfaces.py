"""Repository interfaces (ABCs) for identity."""
from abc import ABC, abstractmethod
from typing import Optional
import uuid

from .entities import User, OAuthToken
from .value_objects import Email, OAuthProvider, PlainPassword


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


class IPasswordBlocklist(ABC):
    @abstractmethod
    def is_common_password(self, password: PlainPassword) -> bool:
        """Return whether the password is in a common-password blocklist."""

    @abstractmethod
    def is_compromised_password(self, password: PlainPassword) -> bool:
        """Return whether the password is known to have been compromised."""

    @abstractmethod
    def is_context_specific_password(
        self,
        password: PlainPassword,
        *,
        email: Email | None = None,
        service_name: str | None = None,
    ) -> bool:
        """Return whether the password is derived from account or service context."""


class IPasswordReuseChecker(ABC):
    @abstractmethod
    def is_reused_password(self, password: PlainPassword) -> bool:
        """Return whether the password matches the current or recent passwords."""
