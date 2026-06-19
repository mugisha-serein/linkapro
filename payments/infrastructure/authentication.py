from rest_framework_simplejwt.authentication import JWTAuthentication
from rest_framework_simplejwt.exceptions import InvalidToken
from infrastructure.adapters.jwt_token_service import accepted_identity_token_env
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

        if not jti:
            raise InvalidToken("Malformed token")

        if blacklist.is_blacklisted(jti):
            raise InvalidToken("Token has been revoked")

        if family and blacklist.is_family_blacklisted(family):
            raise InvalidToken("Token family has been revoked")

        if accepted_identity_token_env(token_env, context="access_token_authentication") is None:
            raise InvalidToken("Token environment mismatch")

        return user, validated_token
