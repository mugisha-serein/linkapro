import hashlib
import requests
from django.conf import settings
from rest_framework import serializers

logger = __import__('logging').getLogger('accounts.security')


class HaveIBeenPwnedChecker:
    """
    Check if a password has appeared in known data breaches using the
    HaveIBeenPwned API via k-anonymity endpoint (password is never sent).
    """

    API_URL = 'https://api.pwnedpasswords.com/range/'
    TIMEOUT = 5  # seconds

    @staticmethod
    def check_password(password):
        """
        Check if password exists in HaveIBeenPwned database.
        Uses k-anonymity: only first 5 chars of SHA-1 hash are sent.
        
        Returns: True if password found in breaches, False if safe.
        Raises: serializers.ValidationError if check fails or password is compromised.
        """
        if not password or len(password) < 1:
            return False

        # Generate SHA-1 hash of password
        sha1_hash = hashlib.sha1(password.encode('utf-8')).hexdigest().upper()
        prefix = sha1_hash[:5]
        suffix = sha1_hash[5:]

        try:
            # Query API with only the first 5 characters (k-anonymity)
            response = requests.get(
                f'{HaveIBeenPwnedChecker.API_URL}{prefix}',
                timeout=HaveIBeenPwnedChecker.TIMEOUT,
                headers={'User-Agent': 'LinkaPro/1.0'}
            )
            response.raise_for_status()
        except requests.RequestException as exc:
            # On API failure, log but don't block registration (fail open)
            logger.warning(
                'HaveIBeenPwned API check failed',
                extra={'error': str(exc), 'password_prefix': prefix}
            )
            return False  # Allow registration if API is down

        # Parse response: each line is "HASH_SUFFIX:COUNT"
        for line in response.text.splitlines():
            hash_suffix, count = line.split(':')
            if hash_suffix == suffix:
                logger.warning(
                    'Password found in HaveIBeenPwned breach database',
                    extra={'breach_count': int(count)}
                )
                raise serializers.ValidationError({
                    'password': 'This password has appeared in known data breaches. Choose a different password.'
                })

        return False  # Password is safe


def check_password_breach(password):
    """Convenience wrapper for use in serializer validators."""
    HaveIBeenPwnedChecker.check_password(password)
