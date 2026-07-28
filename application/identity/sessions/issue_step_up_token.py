"""Issue a short-lived step-up access token for an active token family."""

from application.identity.shared.dtos.token_claims import StepUpTokenRequest
from application.identity.shared.ports import IdentityTokenService
from domain.identity.sessions import TokenFamily


class IssueStepUpTokenUseCase:
    def __init__(self, *, token_service: IdentityTokenService) -> None:
        self.token_service = token_service

    def execute(self, *, user_id: str, original_token: str) -> str:
        claims = self.token_service.inspect_access_token(
            original_token,
            context="step_up_token_issue",
        )
        return self.token_service.issue_step_up_token(
            StepUpTokenRequest(
                claims=claims,
                jti=TokenFamily(claims.family).next_token_id(),
            )
        )


__all__ = ["IssueStepUpTokenUseCase"]
