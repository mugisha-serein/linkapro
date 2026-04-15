# Value Object - Immutable Business Concept
from __future__ import annotations

import re
from dataclasses import dataclass


@dataclass(frozen=True)
class Password:
    """
    Password value object.

    Represents a validated password in the business domain.
    Immutable and self-validating with business security rules.
    """

    # Note: In a real implementation, this would store a hashed password,
    # but as a domain object, we focus on validation rules
    hashed_value: str

    def __post_init__(self):
        """Validate password meets business security requirements."""
        self._validate_strength()

    def _validate_strength(self) -> None:
        """Apply business password strength rules."""
        if not self.hashed_value or len(self.hashed_value) < 8:
            raise ValueError("Password hash too short")

        # Additional validation could include:
        # - Minimum length
        # - Character requirements
        # - Dictionary word checks
        # - Common password checks

        # For now, we just ensure it's not empty and has minimum length
        if len(self.hashed_value.strip()) == 0:
            raise ValueError("Password hash cannot be empty")

    @classmethod
    def from_plain_text(cls, plain_password: str) -> Password:
        """
        Create Password from plain text.

        Note: In domain layer, we define the validation rules.
        Actual hashing is done in infrastructure layer.
        """
        if not cls._validate_plain_password(plain_password):
            raise ValueError("Password does not meet security requirements")

        # Return a placeholder - actual hashing happens in infrastructure
        return cls(hashed_value=f"hashed_{plain_password}")

    @staticmethod
    def _validate_plain_password(password: str) -> bool:
        """Validate plain text password against business rules."""
        if len(password) < 8:
            return False

        # Must contain at least one uppercase letter
        if not re.search(r'[A-Z]', password):
            return False

        # Must contain at least one lowercase letter
        if not re.search(r'[a-z]', password):
            return False

        # Must contain at least one digit
        if not re.search(r'\d', password):
            return False

        # Must contain at least one special character
        if not re.search(r'[!@#$%^&*(),.?":{}|<>]', password):
            return False

        # Check for common weak passwords
        weak_passwords = ['password', '123456', 'qwerty', 'admin']
        if password.lower() in weak_passwords:
            return False

        return True

    def __str__(self) -> str:
        # Never reveal the actual password/hash
        return "***"