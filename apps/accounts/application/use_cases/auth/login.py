# No Business Logic Here
from __future__ import annotations

import hashlib
from dataclasses import dataclass
from uuid import uuid4

from django.db import transaction
from django.utils import timezone

from apps.accounts.application.dto.auth_dto import LoginCommand, LoginResult
from apps.accounts.application.ports import CredentialVerifier, TokenIssuer
from apps.accounts.infrastructure.db.models import DeviceFingerprint, LoginActivity, User, UserSession
from apps.accounts.infrastructure.db.repositories import (
    DeviceRepository,
    LoginActivityRepository,
    SessionRepository,
    TokenRepository,
    UserRepository,
)


@dataclass(slots=True)
class LoginUseCase:
    user_repository: UserRepository
    device_repository: DeviceRepository
    session_repository: SessionRepository
    token_repository: TokenRepository
    login_activity_repository: LoginActivityRepository
    credential_verifier: CredentialVerifier
    token_issuer: TokenIssuer

    def execute(self, command: LoginCommand) -> LoginResult:
        normalized_email = self._normalize_email(command.email)

        with transaction.atomic():
            user = self.user_repository.get_by_email(normalized_email)
            if user is None:
                return LoginResult(
                    authenticated=False,
                    status=LoginActivity.Status.FAILED,
                    failure_reason="INVALID_CREDENTIALS",
                )

            verification = self.credential_verifier.verify(user=user, password=command.password)
            if not verification.authenticated:
                activity = self._write_login_activity(
                    user=user,
                    command=command,
                    status=self._activity_status(verification.status),
                    failure_reason=verification.failure_reason,
                    session=None,
                    device=None,
                    tokens=None,
                )
                return LoginResult(
                    authenticated=False,
                    status=activity.status,
                    failure_reason=verification.failure_reason,
                    user=user,
                    activity=activity,
                )

            issued_tokens = self.token_issuer.issue_login_tokens(user=user, session_key=uuid4().hex)
            device = self._upsert_device(user=user, command=command, issued_tokens=issued_tokens)
            session = self.session_repository.create(
                user=user,
                device=device,
                session_key=issued_tokens.session_key,
                refresh_token_jti=issued_tokens.refresh_token_jti,
                family_id=issued_tokens.family_id,
                ip_address=command.ip_address,
                user_agent=command.user_agent,
                expires_at=issued_tokens.refresh_expires_at,
                state=UserSession.SessionState.ACTIVE,
                revoked_at=None,
            )
            refresh_token = self.token_repository.create(
                user=user,
                session=session,
                jti=issued_tokens.refresh_token_jti,
                token_hash=issued_tokens.refresh_token_hash,
                family_id=issued_tokens.family_id,
                issued_at=issued_tokens.issued_at,
                expires_at=issued_tokens.refresh_expires_at,
            )

            user.last_login = issued_tokens.issued_at
            self.user_repository.save(user, update_fields=["last_login", "updated_at"])

            activity = self._write_login_activity(
                user=user,
                command=command,
                status=LoginActivity.Status.SUCCESS,
                failure_reason=None,
                session=session,
                device=device,
                tokens=issued_tokens,
            )

            return LoginResult(
                authenticated=True,
                status=LoginActivity.Status.SUCCESS,
                user=user,
                device=device,
                session=session,
                refresh_token=refresh_token,
                activity=activity,
                tokens=issued_tokens,
            )

    def __call__(self, command: LoginCommand) -> LoginResult:
        return self.execute(command)

    def _upsert_device(
        self,
        user: User,
        command: LoginCommand,
        issued_tokens,
    ) -> DeviceFingerprint:
        now = issued_tokens.issued_at
        existing = self.device_repository.get_by_user_and_fingerprint_hash(
            user_id=user.id,
            fingerprint_hash=command.fingerprint_hash,
        )

        fields = {
            "user": user,
            "fingerprint_hash": command.fingerprint_hash,
            "user_agent": command.user_agent,
            "device_type": command.device_type or "",
            "browser": command.browser or "",
            "os": command.os or "",
            "timezone": command.timezone or "",
            "language": command.language or "",
            "ip_cidr": command.ip_cidr or "",
            "canvas_hash": command.canvas_hash,
            "webgl_hash": command.webgl_hash,
            "last_session_key": issued_tokens.session_key,
            "last_family_id": issued_tokens.family_id,
            "last_seen_at": now,
            "updated_at": now,
        }

        if existing is None:
            return self.device_repository.create(**fields)

        self.device_repository.update_by_id(existing.id, **fields)
        refreshed = self.device_repository.get_by_id(existing.id)
        return refreshed or existing

    def _write_login_activity(
        self,
        user: User,
        command: LoginCommand,
        status: str,
        failure_reason: str | None,
        session: UserSession | None,
        device: DeviceFingerprint | None,
        tokens,
    ) -> LoginActivity:
        created_at = timezone.now()
        return self.login_activity_repository.create(
            user=user,
            session=session,
            device=device,
            ip_hash=self._hash_text(command.ip_address),
            country_code=command.country_code,
            user_agent=command.user_agent,
            device_type=command.device_type,
            status=status,
            failure_reason=failure_reason,
            event_hash=self._build_event_hash(
                user_id=str(user.id),
                status=status,
                ip_address=command.ip_address,
                session_key=tokens.session_key if tokens is not None else "",
                fingerprint_hash=command.fingerprint_hash,
                created_at=created_at,
            ),
            created_at=created_at,
        )

    def _activity_status(self, status: str) -> str:
        if status == LoginActivity.Status.BLOCKED:
            return LoginActivity.Status.BLOCKED
        return LoginActivity.Status.FAILED

    def _normalize_email(self, email: str) -> str:
        return email.strip().lower()

    def _hash_text(self, value: str) -> str:
        return hashlib.sha256(value.encode("utf-8")).hexdigest()

    def _build_event_hash(
        self,
        user_id: str,
        status: str,
        ip_address: str,
        session_key: str,
        fingerprint_hash: str,
        created_at,
    ) -> str:
        payload = "|".join(
            [
                user_id,
                status,
                ip_address,
                session_key,
                fingerprint_hash,
                created_at.isoformat(),
                uuid4().hex,
            ]
        )
        return hashlib.sha256(payload.encode("utf-8")).hexdigest()
