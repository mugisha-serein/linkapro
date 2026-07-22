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
from django_app.identity.session_tracking import (
    SESSION_ID_CLAIM,
    revoke_identity_session,
    touch_identity_session,
)
from application.identity.ports import ITokenBlacklist
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
        session_id = token.get(SESSION_ID_CLAIM)
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
            revoke_identity_session(session_id=session_id, token_family=family, reason="refresh_reuse_detected")
            raise ValueError("Token has been revoked")
        if self.blacklist.is_family_blacklisted(family):
            self.blacklist.blacklist(jti, ttl=self._remaining_ttl(token))
            revoke_identity_session(session_id=session_id, token_family=family, reason="token_family_revoked")
            raise ValueError("Token family has been revoked")
        if is_token_revoked_for_user(user_id, issued_at):
            self.blacklist.blacklist_family(family)
            revoke_identity_session(session_id=session_id, token_family=family, reason="user_sessions_revoked")
            raise ValueError("Token has been revoked")
        if not token_version_matches_active_user(user_id, token_version):
            self.blacklist.blacklist_family(family)
            revoke_identity_session(session_id=session_id, token_family=family, reason="session_version_mismatch")
            raise ValueError("Token session is no longer valid")

        touch_identity_session(session_id, family)

        # Blacklist the used refresh token
        self.blacklist.blacklist(jti, ttl=self._remaining_ttl(token))

        bootstrap_claims = self._fresh_bootstrap_claims(user_id, session_id)

        # Generate new tokens with same security claims (but fresh user bootstrap claims and new jti)
        new_refresh = RefreshToken()
        new_refresh["user_id"] = token["user_id"]
        new_refresh["scope"] = token.get("scope", "")
        new_refresh["env"] = expected_env
        new_refresh["step_up"] = token.get("step_up", False)
        new_refresh["family"] = family
        if session_id:
            new_refresh[SESSION_ID_CLAIM] = str(session_id)
        new_refresh["jti"] = str(uuid.uuid4())
        self._apply_bootstrap_claims(new_refresh, bootstrap_claims)

        new_access = new_refresh.access_token
        new_access["user_id"] = token["user_id"]
        new_access["scope"] = token.get("scope", "")
        new_access["env"] = expected_env
        new_access["step_up"] = token.get("step_up", False)
        new_access["family"] = family
        if session_id:
            new_access[SESSION_ID_CLAIM] = str(session_id)
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
        session_id = token.get(SESSION_ID_CLAIM)
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
        revoke_identity_session(session_id=session_id, token_family=family, reason="user_signed_out")

    def issue_step_up_token(self, user_id: str, original_token: dict) -> str:
        """Issue a short‑lived (5 min) access token with step_up=True."""
        from rest_framework_simplejwt.tokens import AccessToken

        token = AccessToken()
        token["user_id"] = user_id
        token["scope"] = original_token.get("scope", "")
        token_env = original_token.get("env")
        expected_env = self._token_env()
        family = original_token.get("family")
        session_id = original_token.get(SESSION_ID_CLAIM)
        if accepted_identity_token_env(token_env, context="step_up_token_issue") is None:
            raise ValueError("Token environment mismatch")
        if not family:
            raise ValueError("Malformed token family")
        token["env"] = expected_env
        token["family"] = family
        if session_id:
            token[SESSION_ID_CLAIM] = str(session_id)
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
    def _fresh_bootstrap_claims(user_id, session_id: str | None = None) -> dict:
        from django_app.identity.models import User

        user = User.objects.filter(id=user_id, is_active=True).first()
        if not user:
            raise ValueError("User is no longer active")

        has_password = bool(user.password)
        display_name = f"{user.first_name} {user.last_name}".strip() or user.email
        claims = {
            "id": str(user.id),
            "email": user.email,
            "role": user.role,
            "first_name": user.first_name,
            "last_name": user.last_name,
            "display_name": display_name,
            "avatar": None,
            "created_at": user.created_at.isoformat() if user.created_at else None,
            "last_login": user.last_login.isoformat() if user.last_login else None,
            "is_active": user.is_active,
            "is_verified": user.is_verified,
            "has_password": has_password,
            "requires_password_setup": not has_password,
            "two_factor_enabled": user.two_factor_enabled,
            AUTH_TOKEN_VERSION_CLAIM: user.auth_token_version,
            "is_authenticated": True,
            "onboarding_complete": bool(user.is_verified and has_password),
        }
        if session_id:
            claims[SESSION_ID_CLAIM] = str(session_id)
        return claims

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
            SESSION_ID_CLAIM,
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
