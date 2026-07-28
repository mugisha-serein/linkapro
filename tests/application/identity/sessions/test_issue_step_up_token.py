from unittest.mock import Mock

from application.identity.sessions import IssueStepUpTokenUseCase
from application.identity.shared.dtos import AccessTokenClaims, TokenBootstrapClaims


def test_issue_step_up_token_uses_typed_access_claims():
    claims = AccessTokenClaims(
        user_id="user-id",
        family="family-id",
        session_id="session-id",
        scope="payments:write",
        bootstrap_claims=TokenBootstrapClaims({"id": "user-id"}),
    )
    token_service = Mock()
    token_service.inspect_access_token.return_value = claims
    token_service.issue_step_up_token.return_value = "step-up-token"

    result = IssueStepUpTokenUseCase(token_service=token_service).execute(
        user_id="user-id",
        original_token="access-token",
    )

    assert result == "step-up-token"
    token_service.inspect_access_token.assert_called_once_with(
        "access-token",
        context="step_up_token_issue",
    )
    request = token_service.issue_step_up_token.call_args.args[0]
    assert request.claims is claims
    assert request.jti
