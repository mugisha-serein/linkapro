import logging
import hashlib
import hmac
import uuid
from typing import Optional
from datetime import datetime, timedelta, timezone

import jwt
from django.conf import settings
from django.core.exceptions import ImproperlyConfigured
from django.utils import timezone as django_timezone
from rest_framework_simplejwt.tokens import (
    AccessToken as SimpleAccessToken,
    RefreshToken,
)
from rest_framework_simplejwt.exceptions import TokenError

from application.identity.shared.dtos.token_claims import (
    AccessTokenClaims,
    IssuedTokenPair,
    MfaLoginGrant,
    RefreshTokenClaims,
    RotatedTokenPairRequest,
    StepUpTokenRequest,
    TokenBootstrapClaims,
)
from application.identity.shared.ports import SESSION_ID_CLAIM
from domain.identity.sessions import MalformedRefreshToken, TokenFamily

logger = logging.getLogger(__name__)

AUTH_TOKEN_VERSION_CLAIM = "auth_token_version"


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
    def _apply_session_claims(token, bootstrap_claims: dict | None) -> None:
        if not bootstrap_claims:
            return
        for key in (SESSION_ID_CLAIM, "scope", "step_up"):
            value = bootstrap_claims.get(key)
            if value is not None:
                token[key] = value

    @staticmethod
    def _apply_auth_token_version(token, auth_token_version: int | None, bootstrap_claims: dict | None) -> None:
        if bootstrap_claims and bootstrap_claims.get(AUTH_TOKEN_VERSION_CLAIM) is not None:
            token[AUTH_TOKEN_VERSION_CLAIM] = int(bootstrap_claims[AUTH_TOKEN_VERSION_CLAIM])
            return
        token[AUTH_TOKEN_VERSION_CLAIM] = int(auth_token_version or 0)

    def create_access_token(
        self,
        user_id: str,
        role: str,
        family_id: str | None = None,
        bootstrap_claims: dict | None = None,
        auth_token_version: int | None = None,
    ) -> str:
        token = SimpleAccessToken()
        token["user_id"] = user_id
        token["role"] = role
        token["env"] = self._token_env()
        token["step_up"] = False
        if family_id:
            token["family"] = family_id
        self._apply_session_claims(token, bootstrap_claims)
        self._apply_auth_token_version(token, auth_token_version, bootstrap_claims)
        return str(token)

    def create_refresh_token(
        self,
        user_id: str,
        role: str | None = None,
        family_id: str | None = None,
        bootstrap_claims: dict | None = None,
        auth_token_version: int | None = None,
    ) -> str:
        token = RefreshToken()
        token["user_id"] = user_id
        token["env"] = self._token_env()
        token["step_up"] = False
        if role:
            token["role"] = role
        if family_id:
            token["family"] = family_id
        self._apply_session_claims(token, bootstrap_claims)
        self._apply_auth_token_version(token, auth_token_version, bootstrap_claims)
        return str(token)

    def create_session_tokens(
        self,
        user_id: str,
        role: str,
        bootstrap_claims: dict | None = None,
        auth_token_version: int | None = None,
    ) -> tuple[str, str]:
        family_id = str(uuid.uuid4())
        access = self.create_access_token(
            user_id,
            role,
            family_id=family_id,
            bootstrap_claims=bootstrap_claims,
            auth_token_version=auth_token_version,
        )
        refresh = self.create_refresh_token(
            user_id,
            role,
            family_id=family_id,
            bootstrap_claims=bootstrap_claims,
            auth_token_version=auth_token_version,
        )
        return access, refresh

    def inspect_refresh_token(self, refresh_token: str, *, context: str) -> RefreshTokenClaims:
        try:
            token = RefreshToken(refresh_token)
        except TokenError:
            raise MalformedRefreshToken("Invalid refresh token")

        jti = token.get("jti")
        family = token.get("family")
        if not jti:
            raise MalformedRefreshToken("Malformed refresh token")
        if not family:
            raise MalformedRefreshToken("Malformed refresh token family")
        if accepted_identity_token_env(token.get("env"), context=context) is None:
            raise MalformedRefreshToken("Token environment mismatch")

        return RefreshTokenClaims(
            jti=str(jti),
            family=TokenFamily(str(family)),
            user_id=str(token.get("user_id")) if token.get("user_id") else None,
            session_id=str(token.get(SESSION_ID_CLAIM)) if token.get(SESSION_ID_CLAIM) else None,
            issued_at=token.get("iat"),
            auth_token_version=token.get(AUTH_TOKEN_VERSION_CLAIM),
            raw=refresh_token,
            expires_at=int(token["exp"]),
            role=str(token.get("role", "")),
            scope=str(token.get("scope", "")),
            step_up=bool(token.get("step_up", False)),
        )

    def issue_rotated_pair(self, request: RotatedTokenPairRequest) -> IssuedTokenPair:
        claims = request.claims
        expected_env = self._token_env()
        bootstrap_values = request.bootstrap_claims.values

        new_refresh = RefreshToken()
        new_refresh["user_id"] = claims.user_id
        if claims.role:
            new_refresh["role"] = claims.role
        new_refresh["scope"] = claims.scope
        new_refresh["env"] = expected_env
        new_refresh["step_up"] = claims.step_up
        new_refresh["family"] = claims.family.id
        if claims.session_id:
            new_refresh[SESSION_ID_CLAIM] = str(claims.session_id)
        new_refresh["jti"] = request.refresh_jti
        self._apply_auth_token_version(new_refresh, claims.auth_token_version, bootstrap_values)

        new_access = new_refresh.access_token
        new_access["user_id"] = claims.user_id
        if claims.role:
            new_access["role"] = claims.role
        new_access["scope"] = claims.scope
        new_access["env"] = expected_env
        new_access["step_up"] = claims.step_up
        new_access["family"] = claims.family.id
        if claims.session_id:
            new_access[SESSION_ID_CLAIM] = str(claims.session_id)
        new_access["jti"] = request.access_jti
        self._apply_auth_token_version(new_access, claims.auth_token_version, bootstrap_values)

        return IssuedTokenPair(
            access_token=str(new_access),
            refresh_token=str(new_refresh),
            bootstrap_claims=request.bootstrap_claims,
        )

    def inspect_access_token(self, access_token: str, *, context: str) -> AccessTokenClaims:
        try:
            token = SimpleAccessToken(access_token)
        except TokenError:
            raise MalformedRefreshToken("Invalid access token")

        family = token.get("family")
        if accepted_identity_token_env(token.get("env"), context=context) is None:
            raise MalformedRefreshToken("Token environment mismatch")
        if not family:
            raise MalformedRefreshToken("Malformed token family")

        return AccessTokenClaims(
            user_id=str(token.get("user_id")) if token.get("user_id") else "",
            family=str(family),
            session_id=str(token.get(SESSION_ID_CLAIM)) if token.get(SESSION_ID_CLAIM) else None,
            scope=str(token.get("scope", "")),
            bootstrap_claims=TokenBootstrapClaims(self._bootstrap_claims(token)),
        )

    def issue_step_up_token(self, request: StepUpTokenRequest) -> str:
        claims = request.claims
        token = SimpleAccessToken()
        token["user_id"] = claims.user_id
        token["scope"] = claims.scope
        token["env"] = self._token_env()
        token["family"] = claims.family
        if claims.session_id:
            token[SESSION_ID_CLAIM] = str(claims.session_id)
        token["step_up"] = True
        token["jti"] = request.jti
        self._apply_auth_token_version(
            token,
            None,
            (claims.bootstrap_claims or TokenBootstrapClaims({})).values,
        )
        token.set_exp(lifetime=timedelta(minutes=5))
        return str(token)

    def create_password_reset_token(self, user_id: str) -> str:
        now = datetime.now(timezone.utc)
        payload = {
            "user_id": user_id,
            "token_type": "password_reset",
            "jti": str(uuid.uuid4()),
            "env": self._token_env(),
            "exp": now + settings.PASSWORD_RESET_TIMEOUT,
            "iat": now,
        }
        return jwt.encode(payload, settings.SECRET_KEY, algorithm="HS256")

    def issue_password_reset_token(self, user) -> str:
        from django.db import transaction
        from django_app.identity.models import PasswordResetToken

        token = self.create_password_reset_token(str(user.id))
        payload = self.decode_password_reset_token_payload(token)
        if not payload:
            raise ValueError("Unable to issue password reset token")

        now = django_timezone.now()
        with transaction.atomic():
            PasswordResetToken.objects.filter(
                user=user,
                status=PasswordResetToken.Status.ACTIVE,
            ).update(status=PasswordResetToken.Status.REVOKED, updated_at=now)
            PasswordResetToken.objects.create(
                user=user,
                jti=payload["jti"],
                token_hash=password_reset_token_hash(token),
                status=PasswordResetToken.Status.ACTIVE,
                requested_at=payload.get("iat_datetime", now),
                expires_at=payload["exp_datetime"],
            )

        logger.info(
            "password_reset_token_issued",
            extra={"user_id": str(user.id), "jti": payload["jti"]},
        )
        return token

    def decode_password_reset_token_payload(self, token_str: str) -> Optional[dict]:
        try:
            payload = jwt.decode(
                token_str, settings.SECRET_KEY, algorithms=["HS256"]
            )
            if payload.get("token_type") != "password_reset":
                return None
            if self._enforce_env(payload) is None:
                return None
            if not payload.get("user_id") or not payload.get("jti") or not payload.get("exp"):
                logger.warning("password_reset_token_rejected", extra={"reason": "missing_required_claim"})
                return None
            payload["exp_datetime"] = _timestamp_to_datetime(payload["exp"])
            payload["iat_datetime"] = _timestamp_to_datetime(payload["iat"]) if payload.get("iat") else None
            return payload
        except jwt.PyJWTError:
            return None

    def verify_password_reset_token_once(self, token_str: str):
        from django_app.identity.models import PasswordResetToken

        payload = self.decode_password_reset_token_payload(token_str)
        if not payload:
            logger.warning("password_reset_token_rejected", extra={"reason": "invalid_jwt"})
            return None

        now = django_timezone.now()
        token_hash = password_reset_token_hash(token_str)
        token_record = (
            PasswordResetToken.objects.select_for_update()
            .filter(
                user_id=payload.get("user_id"),
                jti=payload.get("jti"),
                token_hash=token_hash,
            )
            .first()
        )
        if not token_record:
            logger.warning(
                "password_reset_token_rejected",
                extra={"reason": "not_tracked", "user_id": payload.get("user_id"), "jti": payload.get("jti")},
            )
            return None
        if token_record.status != PasswordResetToken.Status.ACTIVE:
            event_name = (
                "password_reset_token_reuse_attempt"
                if token_record.status == PasswordResetToken.Status.USED
                else "password_reset_token_rejected"
            )
            logger.warning(
                event_name,
                extra={"reason": token_record.status, "user_id": str(token_record.user_id), "jti": token_record.jti},
            )
            return None
        if token_record.expires_at <= now:
            token_record.status = PasswordResetToken.Status.EXPIRED
            token_record.save(update_fields=["status", "updated_at"])
            logger.info(
                "password_reset_token_expired",
                extra={"user_id": str(token_record.user_id), "jti": token_record.jti},
            )
            return None
        return payload.get("user_id"), token_record

    def create_email_verification_token(self, user_id: str, challenge_id: str) -> str:
        now = datetime.now(timezone.utc)
        payload = {
            "user_id": user_id,
            "token_type": "email_verify",
            "env": self._token_env(),
            "exp": now + settings.EMAIL_VERIFICATION_TIMEOUT,
            "iat": now,
        }
        payload["challenge_id"] = challenge_id
        return jwt.encode(payload, settings.SECRET_KEY, algorithm="HS256")

    def verify_email_verification_token(self, token_str) -> Optional[str]:
        if hasattr(token_str, "reveal_for_email_verification"):
            token_str = token_str.reveal_for_email_verification()
        try:
            payload = jwt.decode(
                token_str, settings.SECRET_KEY, algorithms=["HS256"]
            )
            if payload.get("token_type") != "email_verify":
                return None
            if self._enforce_env(payload) is None:
                return None
            return payload.get("challenge_id")
        except jwt.PyJWTError:
            return None

    def create_temp_token(self, user_id: str, challenge_id: str) -> str:
        now = datetime.now(timezone.utc)
        payload = {
            "user_id": user_id,
            "challenge_id": challenge_id,
            "purpose": "2fa",
            "jti": str(uuid.uuid4()),
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

    def inspect_mfa_login_grant(self, temp_token: str) -> MfaLoginGrant | None:
        payload = self.verify_temp_token(temp_token)
        if not payload:
            return None
        try:
            return MfaLoginGrant(
                grant_id=str(payload["jti"]),
                account_id=uuid.UUID(str(payload["user_id"])),
                expires_at=datetime.fromtimestamp(float(payload["exp"]), tz=timezone.utc),
                challenge_id=uuid.UUID(str(payload["challenge_id"])),
            )
        except (KeyError, TypeError, ValueError, OSError):
            return None

    @staticmethod
    def _bootstrap_claims(token) -> dict:
        keys = (
            "role",
            AUTH_TOKEN_VERSION_CLAIM,
            SESSION_ID_CLAIM,
        )
        claims = {key: token.get(key) for key in keys if token.get(key) is not None}
        if "id" not in claims and token.get("user_id") is not None:
            claims["id"] = str(token.get("user_id"))
        if "is_authenticated" not in claims:
            claims["is_authenticated"] = True
        return claims


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
    allow_legacy_payment_env = bool(getattr(settings, "ACCEPT_LEGACY_PAYMENT_ENV_TOKENS", False))
    if allow_legacy_payment_env and legacy_env and token_env == legacy_env:
        logger.warning(
            "legacy_payment_env_token_accepted_for_identity",
            extra={"context": context, "token_env": token_env, "expected_env": expected_env},
        )
        return expected_env

    logger.warning(
        "identity_token_env_mismatch",
        extra={"context": context, "token_env": token_env, "expected_env": expected_env},
    )
    return None


def _timestamp_to_datetime(timestamp_value) -> Optional[datetime]:
    if timestamp_value is None:
        return None
    try:
        return datetime.fromtimestamp(int(timestamp_value), tz=timezone.utc)
    except (TypeError, ValueError, OSError):
        return None


def password_reset_value_hash(value: str) -> str:
    hash_key = str(getattr(settings, "PASSWORD_RESET_HASH_KEY", "") or "").strip()
    if not hash_key:
        raise ImproperlyConfigured("PASSWORD_RESET_HASH_KEY must be set")
    key = hash_key.encode("utf-8")
    return hmac.new(key, value.encode("utf-8"), hashlib.sha256).hexdigest()


def password_reset_token_hash(token: str) -> str:
    return password_reset_value_hash(token)
