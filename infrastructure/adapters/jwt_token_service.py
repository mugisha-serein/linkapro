import logging
import uuid
from typing import Optional
from datetime import datetime, timedelta, timezone

import jwt
from django.conf import settings
from rest_framework_simplejwt.tokens import (
    AccessToken as SimpleAccessToken,
    RefreshToken,
)

logger = logging.getLogger(__name__)


class JWTTokenService:
    """
    Hybrid token service:
    - Access/Refresh tokens via djangorestframework-simplejwt (for DRF auth compatibility)
    - Custom short-lived tokens (reset, verification) via PyJWT
    """

    def _token_env(self) -> str:
        env = identity_token_env()
        return env

    def _enforce_env(self, payload: dict) -> Optional[str]:
        return accepted_identity_token_env(payload.get("env"), context="jwt_token_service")

    @staticmethod
    def _apply_bootstrap_claims(token, bootstrap_claims: dict | None) -> None:
        if not bootstrap_claims:
            return
        for key, value in bootstrap_claims.items():
            token[key] = value

    def create_access_token(
        self,
        user_id: str,
        role: str,
        family_id: str | None = None,
        bootstrap_claims: dict | None = None,
    ) -> str:
        token = SimpleAccessToken()
        token["user_id"] = user_id
        token["role"] = role
        token["env"] = self._token_env()
        if family_id:
            token["family"] = family_id
        self._apply_bootstrap_claims(token, bootstrap_claims)
        return str(token)

    def create_refresh_token(
        self,
        user_id: str,
        family_id: str | None = None,
        bootstrap_claims: dict | None = None,
    ) -> str:
        token = RefreshToken()
        token["user_id"] = user_id
        token["env"] = self._token_env()
        if family_id:
            token["family"] = family_id
        self._apply_bootstrap_claims(token, bootstrap_claims)
        return str(token)

    def create_session_tokens(
        self,
        user_id: str,
        role: str,
        bootstrap_claims: dict | None = None,
    ) -> tuple[str, str]:
        family_id = str(uuid.uuid4())
        access = self.create_access_token(
            user_id,
            role,
            family_id=family_id,
            bootstrap_claims=bootstrap_claims,
        )
        refresh = self.create_refresh_token(
            user_id,
            family_id=family_id,
            bootstrap_claims=bootstrap_claims,
        )
        return access, refresh

    def create_password_reset_token(self, user_id: str) -> str:
        now = datetime.now(timezone.utc)
        payload = {
            "user_id": user_id,
            "token_type": "password_reset",
            "env": self._token_env(),
            "exp": now + settings.PASSWORD_RESET_TIMEOUT,
            "iat": now,
        }
        return jwt.encode(payload, settings.SECRET_KEY, algorithm="HS256")

    def verify_password_reset_token(self, token_str: str) -> Optional[str]:
        try:
            payload = jwt.decode(
                token_str, settings.SECRET_KEY, algorithms=["HS256"]
            )
            if payload.get("token_type") != "password_reset":
                return None
            if self._enforce_env(payload) is None:
                return None
            return payload.get("user_id")
        except jwt.PyJWTError:
            return None

    def create_email_verification_token(self, user_id: str) -> str:
        now = datetime.now(timezone.utc)
        payload = {
            "user_id": user_id,
            "token_type": "email_verify",
            "env": self._token_env(),
            "exp": now + settings.EMAIL_VERIFICATION_TIMEOUT,
            "iat": now,
        }
        return jwt.encode(payload, settings.SECRET_KEY, algorithm="HS256")

    def verify_email_verification_token(self, token_str: str) -> Optional[str]:
        try:
            payload = jwt.decode(
                token_str, settings.SECRET_KEY, algorithms=["HS256"]
            )
            if payload.get("token_type") != "email_verify":
                return None
            if self._enforce_env(payload) is None:
                return None
            return payload.get("user_id")
        except jwt.PyJWTError:
            return None

    def create_temp_token(self, user_id: str) -> str:
        now = datetime.now(timezone.utc)
        payload = {
            "user_id": user_id,
            "purpose": "2fa",
            "env": self._token_env(),
            "exp": now + timedelta(minutes=3),
            "iat": now,
        }
        return jwt.encode(payload, settings.SECRET_KEY, algorithm="HS256")

    def verify_temp_token(self, token_str: str) -> Optional[dict]:
        try:
            payload = jwt.decode(token_str, settings.SECRET_KEY, algorithms=["HS256"])
            if payload.get("purpose") != "2fa":
                return None
            if self._enforce_env(payload) is None:
                return None
            return payload
        except jwt.PyJWTError:
            return None


def identity_token_env() -> str:
    env = str(getattr(settings, "TOKEN_ENV", "") or "").strip()
    if not env:
        logger.error("identity_token_env_missing")
        raise ValueError("TOKEN_ENV must be configured")
    return env


def accepted_identity_token_env(token_env: str | None, context: str) -> Optional[str]:
    expected_env = identity_token_env()
    if token_env == expected_env:
        return expected_env

    legacy_env = getattr(settings, "PAYMENT_ENV", None)
    accept_legacy = bool(getattr(settings, "ACCEPT_LEGACY_PAYMENT_ENV_TOKENS", True))
    if accept_legacy and legacy_env and token_env == legacy_env:
        logger.warning(
            "legacy_identity_token_env_accepted",
            extra={"context": context, "token_env": token_env, "expected_env": expected_env},
        )
        return expected_env

    logger.warning(
        "identity_token_env_mismatch",
        extra={"context": context, "token_env": token_env, "expected_env": expected_env},
    )
    return None
