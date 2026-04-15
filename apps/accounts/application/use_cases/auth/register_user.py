# No Business Logic Here
from __future__ import annotations

import hashlib
from dataclasses import dataclass
from uuid import uuid4

from django.db import transaction
from django.utils import timezone

from apps.accounts.application.dto.auth_dto import RegisterUserCommand, RegisterUserResult
from apps.accounts.infrastructure.db.models import LoginActivity, User
from apps.accounts.infrastructure.db.repositories import (
    LoginActivityRepository,
    UserRepository,
)


@dataclass(slots=True)
class RegisterUserUseCase:
    user_repository: UserRepository
    login_activity_repository: LoginActivityRepository

    def execute(self, command: RegisterUserCommand) -> RegisterUserResult:
        normalized_email = self._normalize_email(command.email)

        with transaction.atomic():
            # Check if user already exists
            existing_user = self.user_repository.get_by_email(normalized_email)
            if existing_user is not None:
                return RegisterUserResult(
                    success=False,
                    status=LoginActivity.Status.FAILED,
                    failure_reason="USER_ALREADY_EXISTS",
                )

            # Validate role
            if command.role not in [User.Role.PLANNER, User.Role.VENDOR, User.Role.ADMIN]:
                return RegisterUserResult(
                    success=False,
                    status=LoginActivity.Status.FAILED,
                    failure_reason="INVALID_ROLE",
                )

            # Create the user
            user = self.user_repository.create(
                email=normalized_email,
                password=command.password,
                role=command.role,
                is_active=True,
                is_verified=False,
            )

            # Create registration activity
            activity = self._write_registration_activity(user, command)

            return RegisterUserResult(
                success=True,
                status=LoginActivity.Status.SUCCESS,
                user=user,
                activity=activity,
            )

    def __call__(self, command: RegisterUserCommand) -> RegisterUserResult:
        return self.execute(command)

    def _write_registration_activity(
        self,
        user: User,
        command: RegisterUserCommand,
    ) -> LoginActivity:
        created_at = timezone.now()
        return self.login_activity_repository.create(
            user=user,
            session=None,
            device=None,
            ip_hash=self._hash_text(command.ip_address),
            country_code=command.country_code,
            user_agent=command.user_agent,
            device_type=None,
            event_type=LoginActivity.EventType.LOGIN,  # Using LOGIN for registration
            status=LoginActivity.Status.SUCCESS,
            failure_reason=None,
            event_hash=self._build_event_hash(
                user_id=str(user.id),
                email=user.email,
                ip_address=command.ip_address,
                created_at=created_at,
            ),
            created_at=created_at,
        )

    def _normalize_email(self, email: str) -> str:
        return email.strip().lower()

    def _hash_text(self, value: str) -> str:
        return hashlib.sha256(value.encode("utf-8")).hexdigest()

    def _build_event_hash(
        self,
        user_id: str,
        email: str,
        ip_address: str,
        created_at,
    ) -> str:
        payload = "|".join(
            [
                user_id,
                email,
                ip_address,
                created_at.isoformat(),
                uuid4().hex,
            ]
        )
        return hashlib.sha256(payload.encode("utf-8")).hexdigest()