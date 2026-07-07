"""Context-aware password policy for the identity domain."""
from dataclasses import dataclass, field
from enum import Enum
from typing import TYPE_CHECKING

from .value_objects import Email, PlainPassword

if TYPE_CHECKING:
    from .interfaces import IPasswordBlocklist, IPasswordReuseChecker


@dataclass(frozen=True)
class PasswordPolicyContext:
    mfa_enabled: bool
    email: Email | None = None
    service_name: str = "LinkaPro"


class PasswordRejectionReason(str, Enum):
    TOO_SHORT = "too_short"
    TOO_LONG = "too_long"
    COMMON_PASSWORD = "common_password"
    COMPROMISED_PASSWORD = "compromised_password"
    CONTEXT_SPECIFIC = "context_specific"
    REUSED_PASSWORD = "reused_password"


@dataclass(frozen=True)
class PasswordPolicyDecision:
    approved: bool
    rejection_reasons: tuple[PasswordRejectionReason, ...] = field(default_factory=tuple)
    blocklist_checked: bool = False
    reuse_checked: bool = False

    @classmethod
    def approve(
        cls, *, blocklist_checked: bool = False, reuse_checked: bool = False
    ) -> "PasswordPolicyDecision":
        return cls(
            approved=True,
            blocklist_checked=blocklist_checked,
            reuse_checked=reuse_checked,
        )

    @classmethod
    def reject(
        cls,
        reasons: list[PasswordRejectionReason],
        *,
        blocklist_checked: bool = False,
        reuse_checked: bool = False,
    ) -> "PasswordPolicyDecision":
        return cls(
            approved=False,
            rejection_reasons=tuple(reasons),
            blocklist_checked=blocklist_checked,
            reuse_checked=reuse_checked,
        )


class PasswordPolicy:
    MIN_LENGTH_WITHOUT_MFA = 15
    MIN_LENGTH_WITH_MFA = 8
    MAX_LENGTH = 128

    def evaluate(
        self,
        password: PlainPassword,
        context: PasswordPolicyContext,
        *,
        blocklist: "IPasswordBlocklist | None" = None,
        reuse_checker: "IPasswordReuseChecker | None" = None,
    ) -> PasswordPolicyDecision:
        reasons: list[PasswordRejectionReason] = []
        password_length = len(password.reveal_for_password_hashing())
        minimum_length = (
            self.MIN_LENGTH_WITH_MFA
            if context.mfa_enabled
            else self.MIN_LENGTH_WITHOUT_MFA
        )

        if password_length < minimum_length:
            reasons.append(PasswordRejectionReason.TOO_SHORT)
        if password_length > self.MAX_LENGTH:
            reasons.append(PasswordRejectionReason.TOO_LONG)

        blocklist_checked = blocklist is not None
        if blocklist_checked:
            if blocklist.is_common_password(password):
                reasons.append(PasswordRejectionReason.COMMON_PASSWORD)
            if blocklist.is_compromised_password(password):
                reasons.append(PasswordRejectionReason.COMPROMISED_PASSWORD)
            if blocklist.is_context_specific_password(
                password,
                email=context.email,
                service_name=context.service_name,
            ):
                reasons.append(PasswordRejectionReason.CONTEXT_SPECIFIC)

        reuse_checked = reuse_checker is not None
        if reuse_checked and reuse_checker.is_reused_password(password):
            reasons.append(PasswordRejectionReason.REUSED_PASSWORD)

        if reasons:
            return PasswordPolicyDecision.reject(
                reasons,
                blocklist_checked=blocklist_checked,
                reuse_checked=reuse_checked,
            )

        return PasswordPolicyDecision.approve(
            blocklist_checked=blocklist_checked,
            reuse_checked=reuse_checked,
        )
