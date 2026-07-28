"""Password complexity policy."""
import re

from .plain_password import PlainPassword, WeakPasswordError


class PasswordPolicy:
    @staticmethod
    def validate(plain_password: PlainPassword) -> None:
        if len(plain_password.value) < 8:
            raise WeakPasswordError("Password must be at least 8 characters long")
        if len(plain_password.value) > 128:
            raise WeakPasswordError("Password must be at most 128 characters long")
        if not re.search(r"[A-Z]", plain_password.value):
            raise WeakPasswordError("Password must contain at least one uppercase letter")
        if not re.search(r"[a-z]", plain_password.value):
            raise WeakPasswordError("Password must contain at least one lowercase letter")
        if not re.search(r"\d", plain_password.value):
            raise WeakPasswordError("Password must contain at least one digit")
        if not re.search(r"[^A-Za-z0-9\s]", plain_password.value):
            raise WeakPasswordError(
                "Password must contain at least one non-whitespace special character"
            )
