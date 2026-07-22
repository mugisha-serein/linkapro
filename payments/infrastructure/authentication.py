from rest_framework_simplejwt.authentication import JWTAuthentication
from rest_framework_simplejwt.exceptions import InvalidToken
from django_app.identity.session_revocation import (
    AUTH_TOKEN_VERSION_CLAIM,
    is_token_revoked_for_user,
    token_version_matches_user,
)
from django_app.identity.session_tracking import SESSION_ID_CLAIM, identity_session_is_active
from infrastructure.adapters.jwt_token_service import accepted_identity_token_env
from infrastructure.adapters.redis_token_blacklist import RedisTokenBlacklist


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
        session_id = validated_token.get(SESSION_ID_CLAIM)
        token_env = validated_token.get("env")
        user_id = validated_token.get("user_id")
        issued_at = validated_token.get("iat")
        token_version = validated_token.get(AUTH_TOKEN_VERSION_CLAIM)

        if not jti:
            raise InvalidToken("Malformed token")

        if blacklist.is_blacklisted(jti):
            raise InvalidToken("Token has been revoked")

        if family and blacklist.is_family_blacklisted(family):
            raise InvalidToken("Token family has been revoked")

        if is_token_revoked_for_user(user_id, issued_at):
            raise InvalidToken("Token has been revoked")

        if not token_version_matches_user(user_id, token_version):
            raise InvalidToken("Token session version mismatch")

        if not identity_session_is_active(session_id, family):
            raise InvalidToken("Identity session has been revoked")

        if accepted_identity_token_env(token_env, context="access_token_authentication") is None:
            raise InvalidToken("Token environment mismatch")

        return user, validated_token
