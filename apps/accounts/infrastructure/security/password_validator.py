from __future__ import annotations

import re
from django.core.exceptions import ValidationError


class PasswordComplexityValidator:
    """
    Django password validator enforcing strong password policy.
    """

    def __init__(self, min_length: int = 12):
        self.min_length = min_length

        # precompiled patterns (performance optimization)
        self._upper = re.compile(r"[A-Z]")
        self._lower = re.compile(r"[a-z]")
        self._digit = re.compile(r"\d")
        self._symbol = re.compile(r"[^A-Za-z0-9]")

    def validate(self, password, user=None):
        errors = []

        if len(password) < self.min_length:
            errors.append(
                ValidationError(
                    f"Password must be at least {self.min_length} characters long.",
                    code="password_too_short",
                )
            )

        if not self._upper.search(password):
            errors.append(
                ValidationError(
                    "Password must include an uppercase letter.",
                    code="password_no_uppercase",
                )
            )

        if not self._lower.search(password):
            errors.append(
                ValidationError(
                    "Password must include a lowercase letter.",
                    code="password_no_lowercase",
                )
            )

        if not self._digit.search(password):
            errors.append(
                ValidationError(
                    "Password must include a digit.",
                    code="password_no_digit",
                )
            )

        if not self._symbol.search(password):
            errors.append(
                ValidationError(
                    "Password must include a symbol.",
                    code="password_no_symbol",
                )
            )

        if errors:
            raise ValidationError(errors)

    def get_help_text(self) -> str:
        return (
            f"Your password must be at least {self.min_length} characters long and include "
            "an uppercase letter, a lowercase letter, a digit, and a symbol."
        )