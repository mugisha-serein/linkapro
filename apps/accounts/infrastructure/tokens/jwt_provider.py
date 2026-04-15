from __future__ import annotations

import hashlib
from uuid import uuid4

from django.conf import settings
from django.utils import timezone
from rest_framework_simplejwt.tokens import RefreshToken

from apps.accounts.application.dto.auth_dto import IssuedLoginTokens
from apps.accounts.application.ports import TokenIssuer


class JWTProvider(TokenIssuer):
    """
    Infrastructure JWT issuer.

    Responsibility:
    - issue access/refresh tokens
    - attach claims
    - compute hashes
    """

    def issue_login_tokens(self, user, session_key: str) -> IssuedLoginTokens:
        issued_at = timezone.now()
        family_id = uuid4()

        refresh = RefreshToken.for_user(user)

        # -------------------------
        # SAFE CLAIM WRITING
        # -------------------------
        refresh["email"] = user.email
        refresh["role"] = user.role
        refresh["session_key"] = session_key
        refresh["family_id"] = str(family_id)

        access = refresh.access_token
        access["email"] = user.email
        access["role"] = user.role
        access["session_key"] = session_key
        access["family_id"] = str(family_id)

        refresh_token = str(refresh)
        access_token = str(access)

        refresh_lifetime = settings.SIMPLE_JWT["REFRESH_TOKEN_LIFETIME"]
        access_lifetime = settings.SIMPLE_JWT["ACCESS_TOKEN_LIFETIME"]

        # -------------------------
        # SAFE JTI EXTRACTION
        # -------------------------
        refresh_jti = refresh.get("jti")
        if not refresh_jti:
            # fallback deterministic guard
            refresh_jti = self._hash_token(refresh_token)

        return IssuedLoginTokens(
            access_token=access_token,
            refresh_token=refresh_token,
            refresh_token_jti=str(refresh_jti),
            refresh_token_hash=self._hash_token(refresh_token),
            session_key=session_key,
            family_id=family_id,
            issued_at=issued_at,
            access_expires_at=issued_at + access_lifetime,
            refresh_expires_at=issued_at + refresh_lifetime,
        )

    def issue_refresh_tokens(self, user, session, family_id: str) -> IssuedLoginTokens:
        issued_at = timezone.now()

        refresh = RefreshToken.for_user(user)

        # -------------------------
        # SAFE CLAIM WRITING
        # -------------------------
        refresh["email"] = user.email
        refresh["role"] = user.role
        refresh["session_key"] = session.session_key
        refresh["family_id"] = family_id

        access = refresh.access_token
        access["email"] = user.email
        access["role"] = user.role
        access["session_key"] = session.session_key
        access["family_id"] = family_id

        refresh_token = str(refresh)
        access_token = str(access)

        refresh_lifetime = settings.SIMPLE_JWT["REFRESH_TOKEN_LIFETIME"]
        access_lifetime = settings.SIMPLE_JWT["ACCESS_TOKEN_LIFETIME"]

        # -------------------------
        # SAFE JTI EXTRACTION
        # -------------------------
        refresh_jti = refresh.get("jti")
        if not refresh_jti:
            # fallback deterministic guard
            refresh_jti = self._hash_token(refresh_token)

        return IssuedLoginTokens(
            access_token=access_token,
            refresh_token=refresh_token,
            refresh_token_jti=str(refresh_jti),
            refresh_token_hash=self._hash_token(refresh_token),
            session_key=session.session_key,
            family_id=family_id,  # Keep same family
            issued_at=issued_at,
            access_expires_at=issued_at + access_lifetime,
            refresh_expires_at=issued_at + refresh_lifetime,
        )

    # -------------------------
    # CRYPTO SAFE HASHING
    # -------------------------
    @staticmethod
    def _hash_token(token: str) -> str:
        return hashlib.sha256(
            token.encode("utf-8")
        ).hexdigest()