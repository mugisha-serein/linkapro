from rest_framework_simplejwt.authentication import JWTAuthentication
from rest_framework_simplejwt.exceptions import InvalidToken, AuthenticationFailed
from django_app import settings
from payments.infrastructure.redis_blacklist import RedisTokenBlacklist


class HardenedJWTAuthentication(JWTAuthentication):
    def authenticate(self, request):
        # First, standard JWT authentication
        result = super().authenticate(request)
        if result is None:
            return None

        user, validated_token = result

        # Check if token is blacklisted
        blacklist = RedisTokenBlacklist()
        jti = validated_token.get("jti")
        family = validated_token.get("family")
        token_env = validated_token.get("env")
        expected_env = getattr(settings, "PAYMENT_ENV", None)

        if not expected_env:
            raise InvalidToken("Token environment not configured")

        if not jti:
            raise InvalidToken("Malformed token")

        if blacklist.is_blacklisted(jti):
            raise InvalidToken("Token has been revoked")

        if family and blacklist.is_family_blacklisted(family):
            raise InvalidToken("Token family has been revoked")

        if token_env != expected_env:
            raise InvalidToken("Token environment mismatch")

        return user, validated_token
