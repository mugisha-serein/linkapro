from __future__ import annotations

from rest_framework.exceptions import AuthenticationFailed
from rest_framework_simplejwt.authentication import JWTAuthentication
from rest_framework_simplejwt.settings import api_settings

from apps.accounts.infrastructure.db.repositories import UserRepository
from apps.accounts.infrastructure.tokens.revocation_store import RevocationStore


class CustomJWTAuthentication(JWTAuthentication):
    """
    JWT authentication layer with strict revocation enforcement.
    """

    def __init__(
        self,
        revocation_store: RevocationStore | None = None,
        user_repository: UserRepository | None = None,
    ):
        super().__init__()
        self.revocation_store = revocation_store or RevocationStore()
        self.user_repository = user_repository or UserRepository()

    def authenticate(self, request):
        result = super().authenticate(request)

        if result is None:
            return None

        user, validated_token = result

        # -------------------------
        # REQUIRED CLAIMS (STRICT CONTRACT)
        # -------------------------
        token_jti = validated_token.get(api_settings.JTI_CLAIM)
        user_id = validated_token.get(api_settings.USER_ID_CLAIM)
        session_key = validated_token.get("session_key")

        if not token_jti or not user_id:
            raise AuthenticationFailed("Invalid token structure.")

        # -------------------------
        # REVOCATION CHECKS (EXPLICIT BOOLEAN CONTRACT)
        # -------------------------
        if self.revocation_store.get_token_revocation(token_jti) is True:
            raise AuthenticationFailed("Token has been revoked.")

        if session_key and self.revocation_store.get_session_revocation(session_key) is True:
            raise AuthenticationFailed("Session has been revoked.")

        if self.revocation_store.get_user_revocation(str(user_id)) is True:
            raise AuthenticationFailed("User has been revoked.")

        # -------------------------
        # USER VALIDATION (SINGLE SOURCE OF TRUTH)
        # -------------------------
        db_user = self.user_repository.get_by_id(user.id)

        if db_user is None:
            raise AuthenticationFailed("User not found.")

        if db_user.is_active is False:
            raise AuthenticationFailed("User is inactive.")

        return db_user, validated_token