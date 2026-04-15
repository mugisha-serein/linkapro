# No Business Logic Here
from __future__ import annotations

import hashlib
from dataclasses import dataclass
from uuid import uuid4

from django.db import transaction
from django.utils import timezone

from apps.accounts.application.dto.auth_dto import RefreshTokenCommand, RefreshTokenResult
from apps.accounts.application.ports.services import TokenIssuer
from apps.accounts.infrastructure.db.models import LoginActivity, RefreshToken as RefreshTokenModel, UserSession
from apps.accounts.infrastructure.db.repositories import (
    LoginActivityRepository,
    SessionRepository,
    TokenRepository,
)


@dataclass(slots=True)
class RefreshTokenUseCase:
    session_repository: SessionRepository
    token_repository: TokenRepository
    login_activity_repository: LoginActivityRepository
    token_issuer: TokenIssuer

    def execute(self, command: RefreshTokenCommand) -> RefreshTokenResult:
        with transaction.atomic():
            # Find the refresh token
            refresh_token = self.token_repository.get_by_token_hash(
                self._hash_token(command.refresh_token)
            )
            if refresh_token is None:
                return RefreshTokenResult(
                    success=False,
                    status=LoginActivity.Status.FAILED,
                    failure_reason="INVALID_REFRESH_TOKEN",
                )

            # Check if token is revoked
            if refresh_token.revoked_at is not None:
                return RefreshTokenResult(
                    success=False,
                    status=LoginActivity.Status.FAILED,
                    failure_reason="REVOKED_REFRESH_TOKEN",
                )

            # Check if token is expired
            if refresh_token.expires_at <= timezone.now():
                return RefreshTokenResult(
                    success=False,
                    status=LoginActivity.Status.FAILED,
                    failure_reason="EXPIRED_REFRESH_TOKEN",
                )

            # Get the session
            session = refresh_token.session
            if session is None or session.state != UserSession.SessionState.ACTIVE:
                return RefreshTokenResult(
                    success=False,
                    status=LoginActivity.Status.FAILED,
                    failure_reason="INVALID_SESSION",
                )

            now = timezone.now()

            # Revoke the old refresh token
            self.token_repository.update_by_id(
                refresh_token.id,
                revoked_at=now,
                replaced_by_jti=None,  # Will be set after issuing new token
            )

            # Issue new tokens
            issued_tokens = self.token_issuer.issue_refresh_tokens(
                user=session.user,
                session=session,
                family_id=str(refresh_token.family_id),
            )

            # Update replaced_by_jti on old token
            self.token_repository.update_by_id(
                refresh_token.id,
                replaced_by_jti=issued_tokens.refresh_token_jti,
            )

            # Create new refresh token record
            new_refresh_token = self.token_repository.create(
                user=session.user,
                session=session,
                jti=issued_tokens.refresh_token_jti,
                token_hash=issued_tokens.refresh_token_hash,
                family_id=refresh_token.family_id,
                parent_jti=refresh_token.jti,
                issued_at=issued_tokens.issued_at,
                expires_at=issued_tokens.refresh_expires_at,
            )

            # Update session with new refresh token JTI
            self.session_repository.update_by_id(
                session.id,
                refresh_token_jti=issued_tokens.refresh_token_jti,
                last_used_at=now,
            )

            # Refresh the session object
            session.refresh_from_db()

            # Create refresh activity
            activity = self._write_refresh_activity(session, command, issued_tokens)

            return RefreshTokenResult(
                success=True,
                status=LoginActivity.Status.SUCCESS,
                user=session.user,
                session=session,
                refresh_token=new_refresh_token,
                activity=activity,
                tokens=issued_tokens,
            )

    def __call__(self, command: RefreshTokenCommand) -> RefreshTokenResult:
        return self.execute(command)

    def _write_refresh_activity(
        self,
        session: UserSession,
        command: RefreshTokenCommand,
        tokens,
    ) -> LoginActivity:
        created_at = timezone.now()
        return self.login_activity_repository.create(
            user=session.user,
            session=session,
            device=session.device,
            ip_hash=self._hash_text(command.ip_address),
            country_code=command.country_code,
            user_agent=command.user_agent,
            device_type=session.device.device_type if session.device else None,
            event_type=LoginActivity.EventType.TOKEN_REFRESH,
            status=LoginActivity.Status.SUCCESS,
            failure_reason=None,
            event_hash=self._build_event_hash(
                user_id=str(session.user.id),
                session_key=session.session_key,
                ip_address=command.ip_address,
                token_jti=tokens.refresh_token_jti,
                created_at=created_at,
            ),
            created_at=created_at,
        )

    def _hash_text(self, value: str) -> str:
        return hashlib.sha256(value.encode("utf-8")).hexdigest()

    def _hash_token(self, token: str) -> str:
        return hashlib.sha256(token.encode("utf-8")).hexdigest()

    def _build_event_hash(
        self,
        user_id: str,
        session_key: str,
        ip_address: str,
        token_jti: str,
        created_at,
    ) -> str:
        payload = "|".join(
            [
                user_id,
                session_key,
                ip_address,
                token_jti,
                created_at.isoformat(),
                uuid4().hex,
            ]
        )
        return hashlib.sha256(payload.encode("utf-8")).hexdigest()