# domain/services/token_service.py
# Pure Python — no framework, no ORM, no I/O

from __future__ import annotations

from typing import List, Optional

from domain.entities.refresh_token import RefreshToken
from domain.entities.session import Session
from domain.entities.login_activity import LoginActivity
from domain.value_objects import UserId, SessionId, utc_now
from domain.exceptions import (
    TokenReuseDetectedError,
    TokenExpiredError,
    TokenFamilyCompromisedError,
    TokenOrphanedError,
    SessionInvalidError,
)


# ══════════════════════════════════════════════════════════
# TOKEN DOMAIN SERVICE
#
# Enforces all conceptual refresh-token lifecycle rules.
# "Conceptual" means: the domain models the RULES of token
# rotation and reuse detection, without ever touching JWT
# libraries, Redis, or any infrastructure.
#
# Token bytes are never seen here — only IDs and metadata.
# ══════════════════════════════════════════════════════════


class TokenService:
    """
    Domain service for refresh token lifecycle management.

    Enforces:
    - Single-use rotation semantics (RFC-style).
    - Reuse = theft signal → family revocation.
    - Token must always be linked to a valid session.
    - Family compromise is propagated to all tokens in the family.
    """

    # ──────────────────────────────────────────────────────
    # TOKEN ISSUANCE
    # ──────────────────────────────────────────────────────

    def issue_root_token(
        self,
        session: Session,
        user_id: UserId,
        ttl_days: int = 7,
    ) -> RefreshToken:
        """
        Issue the first refresh token for a newly created session.

        Pre-conditions:
        - Session must be valid (ACTIVE, within TTL).
        - Session must belong to the given user.
        """
        if not session.is_valid():
            raise SessionInvalidError(
                f"Cannot issue token for invalid session {session.id}."
            )
        session.assert_owned_by(user_id)

        token = RefreshToken.create_root(
            session_id=session.id,
            user_id=user_id,
            ttl_days=ttl_days,
        )
        token.assert_has_session()
        return token

    # ──────────────────────────────────────────────────────
    # ROTATION
    # ──────────────────────────────────────────────────────

    def rotate_token(
        self,
        current_token: RefreshToken,
        session: Session,
        ttl_days: int = 7,
    ) -> RotationResult:
        """
        Consume the current token and produce its successor.

        Rotation rules enforced:
        1. Token must be ACTIVE and unexpired.
        2. Token family must not be compromised.
        3. Session must still be valid (revocation check).
        4. On success: current token → USED, new token → ACTIVE.

        On any violation: raises the appropriate domain exception.
        The caller MUST handle TokenReuseDetectedError by also
        revoking the associated session.
        """
        # ── Session still valid? ──────────────────────────
        if not session.is_valid():
            raise SessionInvalidError(
                f"Cannot rotate token: session {session.id} is no longer valid."
            )

        # ── Session / token ownership matches? ────────────
        if current_token.session_id != session.id:
            raise TokenOrphanedError(
                f"Token {current_token.id} does not belong to session {session.id}. "
                "Cross-session token use is forbidden."
            )

        # ── Rotation (raises on reuse / expiry / compromise) ──
        successor = RefreshToken.rotate(parent=current_token, ttl_days=ttl_days)
        successor.assert_has_session()

        return RotationResult(
            old_token=current_token,
            new_token=successor,
            reuse_detected=False,
        )

    # ──────────────────────────────────────────────────────
    # REUSE DETECTION
    # ──────────────────────────────────────────────────────

    def detect_reuse(self, token: RefreshToken) -> bool:
        """
        Non-raising predicate: returns True if reuse is detected.
        A USED or REVOKED token being presented counts as reuse.
        """
        return token.detect_reuse()

    def handle_reuse_detected(
        self,
        reused_token: RefreshToken,
        all_family_tokens: List[RefreshToken],
        session: Session,
    ) -> ReuseHandlingResult:
        """
        Respond to a confirmed token reuse event.

        Actions taken (all domain-level decisions, no persistence):
        1. Mark the reused token's family as compromised.
        2. Revoke every token in the family.
        3. Revoke the associated session.

        The caller MUST persist all mutated objects.

        Returns a ReuseHandlingResult describing what was done.
        """
        # ── Invalidate the family ─────────────────────────
        tokens_revoked: List[str] = []
        for t in all_family_tokens:
            if str(t.family_id) == str(reused_token.family_id):
                t.invalidate_family()
                tokens_revoked.append(str(t.id))

        # Ensure the reused token itself is also invalidated
        if str(reused_token.id) not in tokens_revoked:
            reused_token.invalidate_family()
            tokens_revoked.append(str(reused_token.id))

        # ── Revoke the session ────────────────────────────
        session.revoke()

        return ReuseHandlingResult(
            family_id=str(reused_token.family_id),
            tokens_revoked=tokens_revoked,
            session_revoked=True,
        )

    # ──────────────────────────────────────────────────────
    # FAMILY REVOCATION (explicit, e.g. logout)
    # ──────────────────────────────────────────────────────

    def invalidate_token_family(
        self,
        family_id: str,
        all_family_tokens: List[RefreshToken],
    ) -> int:
        """
        Explicitly revoke an entire token family (e.g. on user logout
        or password change).

        Returns the count of tokens revoked.
        """
        count = 0
        for token in all_family_tokens:
            if str(token.family_id) == family_id:
                token.invalidate_family()
                count += 1
        return count


# ══════════════════════════════════════════════════════════
# RESULT VALUE OBJECTS
# ══════════════════════════════════════════════════════════

class RotationResult:
    """Outcome of a successful token rotation."""

    def __init__(
        self,
        old_token: RefreshToken,
        new_token: RefreshToken,
        reuse_detected: bool,
    ) -> None:
        self.old_token = old_token
        self.new_token = new_token
        self.reuse_detected = reuse_detected

    def __repr__(self) -> str:
        return (
            f"<RotationResult "
            f"old={self.old_token.id} "
            f"new={self.new_token.id} "
            f"reuse_detected={self.reuse_detected}>"
        )


class ReuseHandlingResult:
    """Describes what the domain did in response to a reuse event."""

    def __init__(
        self,
        family_id: str,
        tokens_revoked: List[str],
        session_revoked: bool,
    ) -> None:
        self.family_id = family_id
        self.tokens_revoked = tokens_revoked
        self.session_revoked = session_revoked

    def __repr__(self) -> str:
        return (
            f"<ReuseHandlingResult "
            f"family={self.family_id} "
            f"tokens_revoked={len(self.tokens_revoked)} "
            f"session_revoked={self.session_revoked}>"
        )