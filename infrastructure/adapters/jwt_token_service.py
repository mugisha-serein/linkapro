import uuid
from typing import Optional
from datetime import datetime, timedelta, timezone

import jwt
from django.conf import settings
from rest_framework_simplejwt.tokens import (
    AccessToken as SimpleAccessToken,
    RefreshToken,
    TokenError as SimpleTokenError,
)


class JWTTokenService:
    """
    Hybrid token service:
    - Access/Refresh tokens via djangorestframework-simplejwt (for DRF auth compatibility)
    - Custom short-lived tokens (reset, verification) via PyJWT
    """

    def create_access_token(self, user_id: str, role: str) -> str:
        token = SimpleAccessToken()
        token["user_id"] = user_id
        token["role"] = role
        return str(token)

    def create_refresh_token(self, user_id: str) -> str:
        token = RefreshToken()
        token["user_id"] = user_id
        return str(token)

    def create_password_reset_token(self, user_id: str) -> str:
        now = datetime.now(timezone.utc)
        payload = {
            "user_id": user_id,
            "token_type": "password_reset",
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
            return payload.get("user_id")
        except jwt.PyJWTError:
            return None

    def create_email_verification_token(self, user_id: str) -> str:
        now = datetime.now(timezone.utc)
        payload = {
            "user_id": user_id,
            "token_type": "email_verify",
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
            return payload.get("user_id")
        except jwt.PyJWTError:
            return None

    def refresh_access_token(self, refresh_token_str: str) -> Optional[str]:
        try:
            refresh = RefreshToken(refresh_token_str)
            return str(refresh.access_token)
        except SimpleTokenError:
            return None

    def create_temp_token(self, user_id: str) -> str:
        now = datetime.now(timezone.utc)
        payload = {
            "user_id": user_id,
            "purpose": "2fa",
            "exp": now + timedelta(minutes=3),
            "iat": now,
        }
        return jwt.encode(payload, settings.SECRET_KEY, algorithm="HS256")

    def verify_temp_token(self, token_str: str) -> Optional[dict]:
        try:
            payload = jwt.decode(token_str, settings.SECRET_KEY, algorithms=["HS256"])
            if payload.get("purpose") != "2fa":
                return None
            return payload
        except jwt.PyJWTError:
            return None