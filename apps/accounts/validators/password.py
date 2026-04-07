import re
import string
from django.contrib.auth.password_validation import validate_password as django_validate_password
from django.core.exceptions import ValidationError as DjangoValidationError
from rest_framework import serializers

COMMON_PASSWORD_BLACKLIST = {
    '123456', '123456789', 'qwerty', 'password', '12345678', '111111', '1234567',
    'sunshine', 'iloveyou', 'princess', 'admin', 'welcome', '666666', 'abc123',
    'football', '123123', 'monkey', '654321', '!@#$%^&*', 'charlie', 'aa123456',
    'donald', 'password1', 'qwerty123', 'letmein', '1234', '12345', '1234567890',
    '1q2w3e4r', 'passw0rd', 'baseball', 'dragon', 'master', 'shadow', 'superman',
    '696969', 'qwertyuiop', 'hello', 'freedom', 'whatever', 'qazwsx', 'trustno1',
}

COMPLEXITY_PATTERNS = {
    'lowercase letter': r'[a-z]',
    'uppercase letter': r'[A-Z]',
    'digit': r'\d',
    'symbol': r'[' + re.escape(string.punctuation) + r']',
}


def validate_password_policy(password, user=None, check_breach=True):
    """Validate password strength and policy for user-facing flows."""
    errors = []

    if len(password) < 12:
        errors.append('Password must be at least 12 characters long.')

    for label, pattern in COMPLEXITY_PATTERNS.items():
        if not re.search(pattern, password):
            errors.append(f'Password must include at least one {label}.')

    if password.lower() in COMMON_PASSWORD_BLACKLIST:
        errors.append('Password is too common. Choose a more complex password.')

    if password.isdigit():
        errors.append('Password cannot consist of only digits.')

    if password.isalpha():
        errors.append('Password cannot consist of only letters.')

    try:
        django_validate_password(password, user=user)
    except DjangoValidationError as exc:
        errors.extend(exc.messages)

    # Check HaveIBeenPwned breach database
    if check_breach:
        try:
            from ..services.breach_checker import HaveIBeenPwnedChecker
            HaveIBeenPwnedChecker.check_password(password)
        except serializers.ValidationError as exc:
            errors.extend(exc.detail.get('password', []))

    if errors:
        raise serializers.ValidationError({'password': errors})


class PasswordComplexityValidator:
    """Django password validator wrapper for the account password policy."""

    def validate(self, password, user=None):
        validate_password_policy(password, user=user)

    def get_help_text(self):
        return (
            'Your password must be at least 12 characters long, include uppercase and lowercase letters, '
            'include at least one digit, and include at least one symbol. It must also not be a common password.'
        )