import uuid
from datetime import datetime, timedelta, timezone
from typing import Optional, Tuple

from django.conf import settings
from django.core.cache import cache

from django_app.identity.session_revocation import (
    AUTH_TOKEN_VERSION_CLAIM,
    is_token_revoked_for_user,
    token_version_matches_active_user,
)
from payments.application.ports import ITokenBlacklist
from payments.domain.step_up_policy import StepUpPolicy, StepUpPolicyResult
from infrastructure.adapters.jwt_token_service import accepted_identity_token_env, identity_token_env


class TokenCommandHandlers:
    def __init__(self, blacklist: ITokenBlacklist):
        self.blacklist = blacklist

    def _token_env(self) -> str:
        return identity_token_env()

    def refresh_access_token(self, refresh_token: str) -> Tuple[str, str, dict]:
        """Validate refresh token, rotate, and return new access + refresh pair."""
        from rest_framework_simplejwt.tokens import RefreshToken
        from rest_framework_simplejwt.exceptions import TokenError

        try:
            token = RefreshToken(refresh_token)
        except TokenError:
            raise ValueError("Invalid refresh token")

        jti = token.get("jti")
        family = token.get("family")
        token_env = token.get("env")
        user_id = token.get("user_id")
        issued_at = token.get("iat")
        token_version = token.get(AUTH_TOKEN_VERSION_CLAIM)
        expected_env = self._token_env()

        if not jti:
            raise ValueError("Malformed refresh token")
        if not family:
            raise ValueError("Malformed refresh token family")
        if accepted_identity_token_env(token_env, context="refresh_token_rotation") is None:
            raise ValueError("Token environment mismatch")

        # Check if token is blacklisted
        if self.blacklist.is_blacklisted(jti):
            # Token reuse = possible theft → blacklist whole family
            self.blacklist.blacklist_family(family)
            raise ValueError("Token has been revoked")
        if self.blacklist.is_family_blacklisted(family):
            self.blacklist.blacklist(jti, ttl=self._remaining_ttl(token))
            raise ValueError("Token family has been revoked")
        if is_token_revoked_for_user(user_id, issued_at):
            self.blacklist.blacklist_family(family)
            raise ValueError("Token has been revoked")
        if not token_version_matches_active_user(user_id, token_version):
            self.blacklist.blacklist_family(family)
            raise ValueError("Token session is no longer valid")

        # Blacklist the used refresh token
        self.blacklist.blacklist(jti, ttl=self._remaining_ttl(token))

        bootstrap_claims = self._bootstrap_claims(token)

        # Generate new tokens with same claims (but new jti)
        new_refresh = RefreshToken()
        new_refresh["user_id"] = token["user_id"]
        new_refresh["scope"] = token.get("scope", "")
        new_refresh["env"] = expected_env
        new_refresh["step_up"] = token.get("step_up", False)
        new_refresh["family"] = family
        new_refresh["jti"] = str(uuid.uuid4())
        self._apply_bootstrap_claims(new_refresh, bootstrap_claims)

        new_access = new_refresh.access_token
        new_access["user_id"] = token["user_id"]
        new_access["scope"] = token.get("scope", "")
        new_access["env"] = expected_env
        new_access["step_up"] = token.get("step_up", False)
        new_access["family"] = family
        new_access["jti"] = str(uuid.uuid4())
        self._apply_bootstrap_claims(new_access, bootstrap_claims)

        return str(new_access), str(new_refresh), bootstrap_claims

    def revoke_refresh_token(self, refresh_token: str) -> None:
        from rest_framework_simplejwt.tokens import RefreshToken
        from rest_framework_simplejwt.exceptions import TokenError

        try:
            token = RefreshToken(refresh_token)
        except TokenError:
            raise ValueError("Invalid refresh token")

        jti = token.get("jti")
        family = token.get("family")
        token_env = token.get("env")
        expected_env = self._token_env()

        if not jti:
            raise ValueError("Malformed refresh token")
        if not family:
            raise ValueError("Malformed refresh token family")
        if accepted_identity_token_env(token_env, context="refresh_token_revoke") is None:
            raise ValueError("Token environment mismatch")

        ttl = self._remaining_ttl(token)
        self.blacklist.blacklist(jti, ttl=ttl)
        self.blacklist.blacklist_family(family)

    def issue_step_up_token(self, user_id: str, original_token: dict) -> str:
        """Issue a short‑lived (5 min) access token with step_up=True."""
        from rest_framework_simplejwt.tokens import AccessToken

        token = AccessToken()
        token["user_id"] = user_id
        token["scope"] = original_token.get("scope", "")
        token_env = original_token.get("env")
        expected_env = self._token_env()
        family = original_token.get("family")
        if accepted_identity_token_env(token_env, context="step_up_token_issue") is None:
            raise ValueError("Token environment mismatch")
        if not family:
            raise ValueError("Malformed token family")
        token["env"] = expected_env
        token["family"] = family
        token["step_up"] = True
        token["jti"] = str(uuid.uuid4())
        self._apply_bootstrap_claims(token, self._bootstrap_claims(original_token))
        token.set_exp(lifetime=timedelta(minutes=5))
        return str(token)

    @staticmethod
    def _remaining_ttl(token) -> int:
        expires_at = datetime.fromtimestamp(int(token["exp"]), tz=timezone.utc)
        ttl = int((expires_at - datetime.now(timezone.utc)).total_seconds())
        return max(ttl, 1)

    @staticmethod
    def _bootstrap_claims(token) -> dict:
        keys = (
            "email",
            "role",
            "first_name",
            "last_name",
            "display_name",
            "avatar",
            "created_at",
            "last_login",
            "is_active",
            "is_verified",
            "has_password",
            "requires_password_setup",
            "two_factor_enabled",
            AUTH_TOKEN_VERSION_CLAIM,
            "is_authenticated",
            "onboarding_complete",
        )
        claims = {key: token.get(key) for key in keys if token.get(key) is not None}
        if "id" not in claims and token.get("user_id") is not None:
            claims["id"] = str(token.get("user_id"))
        if "is_authenticated" not in claims:
            claims["is_authenticated"] = True
        return claims

    @staticmethod
    def _apply_bootstrap_claims(token, bootstrap_claims: dict) -> None:
        for key, value in bootstrap_claims.items():
            token[key] = value
