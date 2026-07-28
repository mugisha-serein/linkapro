"""Session and refresh-token rotation policy."""
from __future__ import annotations

from dataclasses import dataclass
from enum import Enum

from .session_errors import (
    RefreshTokenReuseDetected,
    SessionError,
    SessionRevoked,
    SessionVersionMismatch,
    TokenFamilyRevoked,
)
from .token_family import TokenFamily


class RefreshRejectionReason(str, Enum):
    REFRESH_REUSE_DETECTED = "refresh_reuse_detected"
    TOKEN_FAMILY_REVOKED = "token_family_revoked"
    USER_SESSIONS_REVOKED = "user_sessions_revoked"
    SESSION_VERSION_MISMATCH = "session_version_mismatch"
    USER_SIGNED_OUT = "user_signed_out"


@dataclass(frozen=True)
class RefreshTokenSnapshot:
    jti: str
    family: TokenFamily
    session_id: str | None
    user_id: str | None
    issued_at: int | None
    auth_token_version: int | None


@dataclass(frozen=True)
class RefreshRotationDecision:
    allowed: bool
    blacklist_presented_token: bool = False
    revoke_family: bool = False
    touch_session: bool = False
    revoke_session: bool = False
    reason: RefreshRejectionReason | None = None
    error: type[SessionError] | None = None


class SessionPolicy:
    def evaluate_refresh_rotation(
        self,
        token: RefreshTokenSnapshot,
        *,
        token_already_used: bool,
        family_revoked: bool,
        user_sessions_revoked: bool,
        token_version_matches_active_user: bool,
    ) -> RefreshRotationDecision:
        if token.family.detect_replay(token_already_used=token_already_used):
            return RefreshRotationDecision(
                allowed=False,
                revoke_family=True,
                revoke_session=True,
                reason=RefreshRejectionReason.REFRESH_REUSE_DETECTED,
                error=RefreshTokenReuseDetected,
            )
        if family_revoked or token.family.revoked:
            return RefreshRotationDecision(
                allowed=False,
                blacklist_presented_token=True,
                revoke_session=True,
                reason=RefreshRejectionReason.TOKEN_FAMILY_REVOKED,
                error=TokenFamilyRevoked,
            )
        if user_sessions_revoked:
            return RefreshRotationDecision(
                allowed=False,
                revoke_family=True,
                revoke_session=True,
                reason=RefreshRejectionReason.USER_SESSIONS_REVOKED,
                error=SessionRevoked,
            )
        if not token_version_matches_active_user:
            return RefreshRotationDecision(
                allowed=False,
                revoke_family=True,
                revoke_session=True,
                reason=RefreshRejectionReason.SESSION_VERSION_MISMATCH,
                error=SessionVersionMismatch,
            )
        return RefreshRotationDecision(
            allowed=True,
            blacklist_presented_token=True,
            touch_session=True,
        )

    def revoke_family_for_sign_out(self, token: RefreshTokenSnapshot) -> RefreshRotationDecision:
        return RefreshRotationDecision(
            allowed=False,
            blacklist_presented_token=True,
            revoke_family=True,
            revoke_session=True,
            reason=RefreshRejectionReason.USER_SIGNED_OUT,
        )
