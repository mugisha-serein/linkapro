"""Verify an account email address."""

import uuid
from typing import Protocol

from application.identity.commands import VerifyEmailCommand
from application.identity.errors import InvalidCredentialsError, UserNotFoundError
from application.identity.shared.ports import IUserRepository
from domain.identity.verification import VerificationCode, VerificationPolicy, VerificationPurpose


class EmailVerificationTokenService(Protocol):
    def verify_email_verification_token(self, token: str) -> str | None:
        ...


class EventOutbox(Protocol):
    def dispatch(self, event) -> None:
        ...


class VerifyEmailUseCase:
    def __init__(
        self,
        *,
        account_repository: IUserRepository,
        token_service: EmailVerificationTokenService,
        event_outbox: EventOutbox,
    ) -> None:
        self.account_repository = account_repository
        self.token_service = token_service
        self.event_outbox = event_outbox

    def execute(self, cmd: VerifyEmailCommand) -> None:
        user_id_str = self.token_service.verify_email_verification_token(cmd.verification_token)
        if not user_id_str:
            raise InvalidCredentialsError("Invalid or expired verification token")

        user_id = uuid.UUID(user_id_str)
        user = self.account_repository.get_by_id(user_id)
        if not user:
            raise UserNotFoundError("User not found")

        verification_policy = VerificationPolicy()
        verification_code = VerificationCode(cmd.verification_token)
        challenge = verification_policy.issue_challenge(
            user_id=user.id,
            purpose=VerificationPurpose.EMAIL,
            code=verification_code,
        )
        verification_policy.verify_challenge(challenge, verification_code)
        user.mark_verified(challenge=challenge)
        self.account_repository.save(user)
        for event in challenge.pull_events():
            self.event_outbox.dispatch(event)
        for event in user.pull_events():
            self.event_outbox.dispatch(event)


__all__ = ["VerifyEmailUseCase"]
