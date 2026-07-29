"""Identity token service port."""

from typing import Protocol

from application.identity.shared.dtos.token_claims import (
    AccessTokenClaims,
    IssuedTokenPair,
    RefreshTokenClaims,
    RotatedTokenPairRequest,
    StepUpTokenRequest,
    MfaLoginGrant,
)


class IdentityTokenService(Protocol):
    def inspect_refresh_token(self, refresh_token: str, *, context: str) -> RefreshTokenClaims:
        ...

    def issue_rotated_pair(self, request: RotatedTokenPairRequest) -> IssuedTokenPair:
        ...

    def inspect_access_token(self, access_token: str, *, context: str) -> AccessTokenClaims:
        ...

    def issue_step_up_token(self, request: StepUpTokenRequest) -> str:
        ...

    def create_temp_token(self, user_id: str, challenge_id: str) -> str:
        ...

    def inspect_mfa_login_grant(self, temp_token: str) -> MfaLoginGrant | None:
        ...


__all__ = [
    "AccessTokenClaims",
    "IdentityTokenService",
    "MfaLoginGrant",
]
