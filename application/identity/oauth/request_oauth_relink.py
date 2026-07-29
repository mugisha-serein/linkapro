"""Request OAuth identity relinking.

Cross-account OAuth relinking is fail-closed until the caller supplies a
separate step-up grant to ConfirmOAuthRelinkUseCase.
"""

from dataclasses import dataclass
import uuid

from application.identity.errors import OAuthRelinkRequiresStepUp
from domain.identity.oauth import OAuthProvider


@dataclass(frozen=True)
class RequestOAuthRelinkCommand:
    target_user_id: uuid.UUID
    provider: OAuthProvider
    provider_user_id: str


class RequestOAuthRelinkUseCase:
    def execute(self, cmd: RequestOAuthRelinkCommand) -> None:
        raise OAuthRelinkRequiresStepUp("OAuth relink requires step-up verification")


__all__ = ["RequestOAuthRelinkCommand", "RequestOAuthRelinkUseCase"]
