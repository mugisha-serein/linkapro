# domain/entities/refresh_token.py
# Pure Python — no framework, no ORM, no I/O

from __future__ import annotations

from dataclasses import dataclass, field
from datetime import datetime, timedelta
from typing import Optional

from domain.value_objects import (
    TokenId,
    SessionId,
    UserId,
    TokenFamilyId,
    TokenStatus,
    utc_now,
)
from domain.exceptions.exception import (
    TokenReuseDetectedError,
    TokenExpiredError,
    TokenFamilyCompromisedError,
    TokenOrphanedError,
)


# ══════════════════════════════════════════════════════════
# REFRESH TOKEN ENTITY
#
# Represents the conceptual right to continue a session.
# Actual token bytes are never held here — only the metadata
# that governs rotation, reuse detection, and family tracking.
#
# Rotation model (RFC-style):
#   1. Client presents token T_n.
#   2. Domain validates T_n → marks it USED, issues T_(n+1).
#   3. If T_n is presented again after being USED → REUSE DETECTED
#      → entire family is REVOKED.
# ══════════════════════════════════════════════════════════

DEFAULT_REFRESH_TTL_DAYS: int = 7


@dataclass
class RefreshToken:
    """
    Conceptual refresh token with rotation and family-tracking semantics.

    Zero-trust rules enforced:
    - Single-use: each token can be consumed exactly once.
    - Reuse = theft signal: invalidates the entire family.
    - Cannot exist without a valid session reference.
    - Family compromise is irreversible.
    """

    id: TokenId
    session_id: SessionId
    user_id: UserId
    family_id: TokenFamilyId
    status: TokenStatus
    issued_at: datetime
    expires_at: datetime
    parent_token_id: Optional[TokenId] = None     # None for family root
    successor_token_id: Optional[TokenId] = None  # set after rotation
    revoked_at: Optional[datetime] = None
    family_compromised: bool = False

    # ── Factory ───────────────────────────────────────────

    @classmethod
    def create_root(
        cls,
        session_id: SessionId,
        user_id: UserId,
        ttl_days: int = DEFAULT_REFRESH_TTL_DAYS,
    ) -> "RefreshToken":
        """
        Issue the first token in a new family (no parent).
        Called on successful authentication.
        """
        now = utc_now()
        return cls(
            id=TokenId.generate(),
            session_id=session_id,
            user_id=user_id,
            family_id=TokenFamilyId.generate(),
            status=TokenStatus.ACTIVE,
            issued_at=now,
            expires_at=now + timedelta(days=ttl_days),
        )

    @classmethod
    def rotate(
        cls,
        parent: "RefreshToken",
        ttl_days: int = DEFAULT_REFRESH_TTL_DAYS,
    ) -> "RefreshToken":
        """
        Consume the parent token and return its successor.

        Enforces:
        - Parent must be ACTIVE and unexpired.
        - Parent must belong to an un-compromised family.
        - Parent is marked USED immediately (before successor is returned).
        """
        parent._assert_rotatable()
        parent._consume()

        now = utc_now()
        successor = cls(
            id=TokenId.generate(),
            session_id=parent.session_id,
            user_id=parent.user_id,
            family_id=parent.family_id,      # same family chain
            status=TokenStatus.ACTIVE,
            issued_at=now,
            expires_at=now + timedelta(days=ttl_days),
            parent_token_id=parent.id,
        )
        parent.successor_token_id = successor.id
        return successor

    # ── Validation helpers ────────────────────────────────

    def _assert_rotatable(self) -> None:
        """Full pre-rotation guard."""
        if self.family_compromised:
            raise TokenFamilyCompromisedError(
                f"Token family {self.family_id} is compromised. "
                "All tokens in this family are revoked."
            )
        if self.status == TokenStatus.REVOKED:
            raise TokenReuseDetectedError(
                f"Token {self.id} has been revoked. "
                "Possible token theft — family invalidated."
            )
        if self.status == TokenStatus.USED:
            # A consumed token presented again = definitive reuse signal
            raise TokenReuseDetectedError(
                f"Token {self.id} has already been used (reuse detected). "
                "Entire family must be revoked."
            )
        if self.status == TokenStatus.EXPIRED or utc_now() >= self.expires_at:
            self.status = TokenStatus.EXPIRED
            raise TokenExpiredError(
                f"Token {self.id} has expired and cannot be rotated."
            )

    def _consume(self) -> None:
        """Mark this token as consumed — single-use semantics."""
        self.status = TokenStatus.USED

    # ── Reuse detection ───────────────────────────────────

    def detect_reuse(self) -> bool:
        """
        Returns True if this token shows signs of reuse.
        A token is reused if it is USED but presented again,
        or if the family is already marked compromised.
        """
        return self.status == TokenStatus.USED or self.family_compromised

    def invalidate_family(self) -> None:
        """
        Mark this token and its entire family as compromised.
        Called when reuse is confirmed. This entity records the fact;
        the application/infrastructure layer must cascade to all siblings.
        """
        self.family_compromised = True
        self.status = TokenStatus.REVOKED
        self.revoked_at = utc_now()

    # ── Validity predicate ────────────────────────────────

    def is_valid(self) -> bool:
        """Non-raising validity check."""
        if self.family_compromised:
            return False
        if self.status != TokenStatus.ACTIVE:
            return False
        if utc_now() >= self.expires_at:
            self.status = TokenStatus.EXPIRED
            return False
        return True

    def assert_has_session(self) -> None:
        """Domain invariant: a token must always reference a session."""
        if not self.session_id:
            raise TokenOrphanedError(
                f"Token {self.id} has no associated session — domain invariant violated."
            )

    # ── Identity ──────────────────────────────────────────

    def __eq__(self, other: object) -> bool:
        if not isinstance(other, RefreshToken):
            return NotImplemented
        return self.id == other.id

    def __hash__(self) -> int:
        return hash(self.id)

    def __repr__(self) -> str:
        return (
            f"<RefreshToken id={self.id} "
            f"family={self.family_id} "
            f"status={self.status.value} "
            f"compromised={self.family_compromised}>"
        )