"""TOTP secret value object."""
import base64
import binascii
import re
from dataclasses import dataclass, field

from domain.identity.shared.secret_value import _contains_control_character, _fingerprint_secret


@dataclass(frozen=True)
class TOTPSecret:
    """Base32‑encoded TOTP secret."""
    value: str = field(repr=False)

    def __post_init__(self):
        if _contains_control_character(self.value):
            raise ValueError("TOTP secret contains unsafe control characters")
        normalized = self.value.strip().upper()
        object.__setattr__(self, "value", normalized)
        unpadded = normalized.rstrip("=")
        if not re.match(r'^[A-Z2-7]+=*$', normalized):
            raise ValueError("Invalid TOTP secret format")
        try:
            base64.b32decode(normalized, casefold=False)
        except (binascii.Error, ValueError):
            raise ValueError("Invalid TOTP secret format") from None
        if "=" in normalized and len(unpadded) < 16:
            raise ValueError("Invalid TOTP secret format")
        if len(unpadded) < 16:
            raise ValueError("TOTP secret must be at least 16 characters long")

    @property
    def raw_value(self) -> str:
        """Deprecated compatibility accessor; prefer reveal_for_totp_verification()."""
        return self.value

    def reveal(self) -> str:
        """Deprecated compatibility accessor; prefer reveal_for_totp_verification()."""
        return self.value

    def reveal_for_totp_verification(self) -> str:
        return self.value

    def fingerprint(self) -> str:
        return _fingerprint_secret(self.value)

    def __str__(self) -> str:
        return "******"

    def __repr__(self) -> str:
        return "TOTPSecret(value='******')"
