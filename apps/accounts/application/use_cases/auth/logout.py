# No Business Logic Here
from __future__ import annotations

import hashlib
from dataclasses import dataclass
from uuid import uuid4

from django.db import transaction
from django.utils import timezone

from apps.accounts.application.dto.auth_dto import LogoutCommand, LogoutResult
from apps.accounts.infrastructure.db.models import LoginActivity, UserSession
from apps.accounts.infrastructure.db.repositories import (
    LoginActivityRepository,
    SessionRepository,
    TokenRepository,
)


@dataclass(slots=True)
class LogoutUseCase:
    session_repository: SessionRepository
    token_repository: TokenRepository
    login_activity_repository: LoginActivityRepository

    def execute(self, command: LogoutCommand) -> LogoutResult:
        with transaction.atomic():
            session = self.session_repository.get_by_session_key(command.session_key)
            if session is None:
                return LogoutResult(
                    success=False,
                    status=LoginActivity.Status.FAILED,
                    failure_reason="SESSION_NOT_FOUND",
                )

            if session.state != UserSession.SessionState.ACTIVE:
                return LogoutResult(
                    success=False,
                    status=LoginActivity.Status.FAILED,
                    failure_reason="SESSION_ALREADY_INACTIVE",
                )

            now = timezone.now()
            # Revoke the session
            self.session_repository.update_by_id(
                session.id,
                state=UserSession.SessionState.REVOKED,
                revoked_at=now,
                revoked_reason="USER_LOGOUT",
            )

            # Revoke the refresh token
            refresh_token = self.token_repository.get_by_jti(session.refresh_token_jti)
            if refresh_token:
                self.token_repository.update_by_id(
                    refresh_token.id,
                    revoked_at=now,
                )

            # Refresh the session object
            session.refresh_from_db()

            # Create logout activity
            activity = self._write_logout_activity(session, command)

            return LogoutResult(
                success=True,
                status=LoginActivity.Status.SUCCESS,
                user=session.user,
                session=session,
                activity=activity,
            )

    def __call__(self, command: LogoutCommand) -> LogoutResult:
        return self.execute(command)

    def _write_logout_activity(
        self,
        session: UserSession,
        command: LogoutCommand,
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
            event_type=LoginActivity.EventType.LOGOUT,
            status=LoginActivity.Status.SUCCESS,
            failure_reason=None,
            event_hash=self._build_event_hash(
                user_id=str(session.user.id),
                session_key=session.session_key,
                ip_address=command.ip_address,
                created_at=created_at,
            ),
            created_at=created_at,
        )

    def _hash_text(self, value: str) -> str:
        return hashlib.sha256(value.encode("utf-8")).hexdigest()

    def _build_event_hash(
        self,
        user_id: str,
        session_key: str,
        ip_address: str,
        created_at,
    ) -> str:
        payload = "|".join(
            [
                user_id,
                session_key,
                ip_address,
                created_at.isoformat(),
                uuid4().hex,
            ]
        )
        return hashlib.sha256(payload.encode("utf-8")).hexdigest()