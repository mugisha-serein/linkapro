"""OAuth access token value object."""
from domain.identity.shared.secret_value import SecretValue


class OAuthAccessToken(SecretValue):
    """OAuth access token. Raw value access must be explicit."""

    def reveal_for_provider_sync(self) -> str:
        return self.value
