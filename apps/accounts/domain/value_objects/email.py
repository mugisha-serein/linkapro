# Value Object - Immutable Business Concept
from __future__ import annotations

import re
from dataclasses import dataclass


@dataclass(frozen=True)
class Email:
    """
    Email value object.

    Represents a validated email address in the business domain.
    Immutable and self-validating.
    """

    value: str

    def __post_init__(self):
        """Validate email format and business rules."""
        self._validate_format()
        self._validate_business_rules()

    def _validate_format(self) -> None:
        """Validate email format using regex."""
        email_pattern = r'^[a-zA-Z0-9._%+-]+@[a-zA-Z0-9.-]+\.[a-zA-Z]{2,}$'
        if not re.match(email_pattern, self.value):
            raise ValueError(f"Invalid email format: {self.value}")

    def _validate_business_rules(self) -> None:
        """Apply business-specific email validation rules."""
        # Email must be lowercase (business rule)
        if self.value != self.value.lower():
            raise ValueError("Email must be lowercase")

        # Email length constraints
        if len(self.value) > 254:  # RFC 5321 limit
            raise ValueError("Email too long")

        # Domain restrictions (example business rule)
        blocked_domains = ['tempmail.com', 'throwaway.com']
        domain = self.value.split('@')[1].lower()
        if domain in blocked_domains:
            raise ValueError(f"Email domain not allowed: {domain}")

    @property
    def domain(self) -> str:
        """Extract domain from email."""
        return self.value.split('@')[1]

    @property
    def local_part(self) -> str:
        """Extract local part from email."""
        return self.value.split('@')[0]

    def __str__(self) -> str:
        return self.value