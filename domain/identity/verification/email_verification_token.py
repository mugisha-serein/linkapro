"""Signed email-verification token value object."""

from dataclasses import dataclass, field

from domain.identity.shared.secret_value import _contains_control_character, _fingerprint_secret

from .verification_errors import InvalidVerificationCode


@dataclass(frozen=True)
class EmailVerificationToken:
    """Signed token used to verify email ownership.

    This is distinct from VerificationCode, which represents a short
    user-entered code such as an MFA code.
    """

    value: str = field(repr=False)

    def __post_init__(self) -> None:
        if not isinstance(self.value, str):
            raise InvalidVerificationCode("Email verification token must be text")
        normalized = self.value.strip()
        if not normalized:
            raise InvalidVerificationCode("Email verification token is required")
        if normalized != self.value:
            raise InvalidVerificationCode("Email verification token cannot have leading or trailing whitespace")
        if _contains_control_character(normalized):
            raise InvalidVerificationCode("Email verification token cannot contain control characters")

    def reveal_for_email_verification(self) -> str:
        return self.value

    def fingerprint(self) -> str:
        return _fingerprint_secret(self.value)

    def __str__(self) -> str:
        return "******"

    def __repr__(self) -> str:
        return "EmailVerificationToken(value='******')"


__all__ = ["EmailVerificationToken"]
