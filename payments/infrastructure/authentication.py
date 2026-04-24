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

        if blacklist.is_blacklisted(jti):
            raise InvalidToken("Token has been revoked")

        if family and blacklist.is_blacklisted(f"family:{family}"):
            raise InvalidToken("Token family has been revoked")

        # Check environment (prevent test tokens in production)
        token_env = validated_token.get("env", "")
        if settings.PAYMENT_ENV == "live" and token_env != "live":
            raise InvalidToken("Test token used in live environment")

        return user, validated_token