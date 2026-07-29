"""OAuth identity persistence port."""

from abc import ABC, abstractmethod
from typing import Optional
import uuid

from domain.identity.oauth import OAuthProvider, OAuthToken


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
    def list_by_user(self, user_id: uuid.UUID) -> tuple[OAuthToken, ...]:
        """Retrieve all linked provider identities for an internal user."""

    @abstractmethod
    def delete_for_user(self, user_id: uuid.UUID, provider: OAuthProvider) -> None:
        """Remove linked provider for user."""


__all__ = ["IOAuthTokenRepository"]
