from dataclasses import dataclass, field
from datetime import datetime, timezone
from uuid import UUID

from domain.exceptions.exception import (
    TokenAlreadyUsedError,
    TokenExpiredError,
    TokenFamilyCompromisedError,
    TokenOrphanError,
)


@dataclass
class RefreshToken:
    """
    Conceptual representation of a session continuation token.

    This entity models ROTATION RULES and REUSE DETECTION only.
    It never contains actual token bytes — that is an infrastructure concern.
    The domain only knows about token lifecycle rules.

    Key concepts:
        - Token family: a chain of rotated tokens sharing a root.
          If any token in the family is reused, the entire family is compromised.
        - Single-use: each token is consumed on rotation.
        - Rotation: consuming a token produces a successor.

    Invariants:
        - Cannot exist without a session_id (orphan rule).
        - Cannot be used after it has been consumed.
        - Reuse of a consumed token signals potential theft.
        - Family compromise invalidates all tokens in the chain.
    """

    id: UUID
    session_id: UUID
    family_id: UUID          # Shared across a rotation chain
    expires_at: datetime
    is_consumed: bool = field(default=False)
    family_compromised: bool = field(default=False)
    parent_token_id: UUID | None = field(default=None)
    created_at: datetime = field(default_factory=lambda: datetime.now(timezone.utc))

    def __post_init__(self) -> None:
        if self.session_id is None:
            raise TokenOrphanError(
                "A refresh token cannot exist without an associated session."
            )

    # ------------------------------------------------------------------
    # Guards
    # ------------------------------------------------------------------

    def assert_usable(self) -> None:
        """
        Assert this token is in a state where it can be used for rotation.

        Checks in order of severity:
            1. Family compromise (highest threat — possible theft in chain)
            2. Already consumed (reuse attempt)
            3. Expiry (time-based invalidity)
        """
        if self.family_compromised:
            raise TokenFamilyCompromisedError(
                f"Token family {self.family_id} is compromised. "
                "All sessions in this family must be invalidated immediately."
            )

        if self.is_consumed:
            raise TokenAlreadyUsedError(
                f"Refresh token {self.id} has already been used. "
                "Possible token reuse attack detected."
            )

        if datetime.now(timezone.utc) >= self.expires_at:
            raise TokenExpiredError(
                f"Refresh token {self.id} has expired."
            )

    # ------------------------------------------------------------------
    # Rotation logic
    # ------------------------------------------------------------------

    def rotate(self) -> "RefreshToken":
        """
        Consume this token and return a conceptual descriptor for its successor.

        Rules:
        - This token becomes consumed (single-use enforced).
        - The successor inherits the same family_id (chain continuity).
        - The successor links back to this token as its parent.

        The caller (application layer) is responsible for persisting the
        successor and setting its expiry. The domain only defines the
        relationship and transition.
        """
        self.assert_usable()
        self.is_consumed = True

        # Return a descriptor — the application layer will assign
        # a real UUID and expiry before persisting.
        from uuid import uuid4
        return RefreshToken(
            id=uuid4(),
            session_id=self.session_id,
            family_id=self.family_id,
            expires_at=self.expires_at,    # Application layer will override
            parent_token_id=self.id,
        )

    # ------------------------------------------------------------------
    # Reuse detection
    # ------------------------------------------------------------------

    def detect_reuse(self) -> bool:
        """
        Returns True if this token has already been consumed.

        Reuse of a consumed token is a strong signal of token theft.
        The caller MUST call invalidate_family() upon detecting reuse.
        """
        return self.is_consumed

    def invalidate_family(self) -> None:
        """
        Mark the entire token family as compromised.

        Once a family is compromised, ALL tokens sharing this family_id
        must be revoked. The application layer is responsible for querying
        and revoking sibling tokens — the domain only marks the flag.
        """
        self.family_compromised = True
