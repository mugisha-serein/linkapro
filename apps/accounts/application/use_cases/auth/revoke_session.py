# No Business Logic Here
from __future__ import annotations

import hashlib
from dataclasses import dataclass
from uuid import uuid4, UUID

from django.db import transaction
from django.utils import timezone

from apps.accounts.application.dto.auth_dto import RevokeSessionCommand, RevokeSessionResult
from apps.accounts.infrastructure.db.models import LoginActivity, UserSession
from apps.accounts.infrastructure.db.repositories import (
    LoginActivityRepository,
    SessionRepository,
    TokenRepository,
)


@dataclass(slots=True)
class RevokeSessionUseCase:
    session_repository: SessionRepository
    token_repository: TokenRepository
    login_activity_repository: LoginActivityRepository

    def execute(self, command: RevokeSessionCommand) -> RevokeSessionResult:
        try:
            session_id = UUID(command.session_id)
        except ValueError:
            return RevokeSessionResult(
                success=False,
                status=LoginActivity.Status.FAILED,
                failure_reason="INVALID_SESSION_ID",
            )

        with transaction.atomic():
            session = self.session_repository.get_by_id(session_id)
            if session is None:
                return RevokeSessionResult(
                    success=False,
                    status=LoginActivity.Status.FAILED,
                    failure_reason="SESSION_NOT_FOUND",
                )

            if session.state != UserSession.SessionState.ACTIVE:
                return RevokeSessionResult(
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
                revoked_reason=command.reason,
            )

            # Revoke associated refresh tokens
            refresh_tokens = self.token_repository.list_by_session(session.id)
            for token in refresh_tokens:
                if token.revoked_at is None:
                    self.token_repository.update_by_id(
                        token.id,
                        revoked_at=now,
                    )

            # Refresh the session object
            session.refresh_from_db()

            # Create revocation activity
            activity = self._write_revocation_activity(session, command)

            return RevokeSessionResult(
                success=True,
                status=LoginActivity.Status.SUCCESS,
                session=session,
                activity=activity,
            )

    def __call__(self, command: RevokeSessionCommand) -> RevokeSessionResult:
        return self.execute(command)

    def _write_revocation_activity(
        self,
        session: UserSession,
        command: RevokeSessionCommand,
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
            event_type=LoginActivity.EventType.LOGOUT,  # Using LOGOUT for session revocation
            status=LoginActivity.Status.SUCCESS,
            failure_reason=None,
            event_hash=self._build_event_hash(
                user_id=str(session.user.id),
                session_key=session.session_key,
                ip_address=command.ip_address,
                reason=command.reason,
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
        reason: str,
        created_at,
    ) -> str:
        payload = "|".join(
            [
                user_id,
                session_key,
                ip_address,
                reason,
                created_at.isoformat(),
                uuid4().hex,
            ]
        )
        return hashlib.sha256(payload.encode("utf-8")).hexdigest()