"""Verify an account email address."""

import uuid
from typing import Protocol

from application.identity.verification.verify_email_command import VerifyEmailCommand
from application.identity.errors import InvalidCredentialsError, UserNotFoundError
from application.identity.shared.ports import EventOutbox, AccountRepository, VerificationChallengeRepository
from domain.identity.verification import (
    EmailVerificationToken,
    VerificationAttemptsExhausted,
    VerificationChallengeConsumed,
    VerificationExpired,
    VerificationPolicy,
    VerificationPurpose,
)


class EmailVerificationTokenService(Protocol):
    def verify_email_verification_token(self, token: EmailVerificationToken) -> str | None:
        ...


class VerifyEmailUseCase:
    def __init__(
        self,
        *,
        account_repository: AccountRepository,
        verification_challenge_repository: VerificationChallengeRepository,
        token_service: EmailVerificationTokenService,
        event_outbox: EventOutbox,
    ) -> None:
        self.account_repository = account_repository
        self.verification_challenge_repository = verification_challenge_repository
        self.token_service = token_service
        self.event_outbox = event_outbox

    def execute(self, cmd: VerifyEmailCommand) -> None:
        challenge_id_str = self.token_service.verify_email_verification_token(cmd.verification_token)
        if not challenge_id_str:
            raise InvalidCredentialsError("Invalid or expired verification token")

        try:
            challenge_id = uuid.UUID(challenge_id_str)
        except ValueError:
            raise InvalidCredentialsError("Invalid or expired verification token")
        challenge = self.verification_challenge_repository.get(challenge_id)
        if not challenge:
            raise InvalidCredentialsError("Invalid or expired verification token")

        user = self.account_repository.get_by_id(challenge.user_id)
        if not user:
            raise UserNotFoundError("User not found")

        verification_policy = VerificationPolicy()
        try:
            challenge.consume()
        except (VerificationAttemptsExhausted, VerificationChallengeConsumed, VerificationExpired):
            self.verification_challenge_repository.save(challenge)
            raise InvalidCredentialsError("Invalid or expired verification token")
        verification_policy.ensure_terminal_challenge_succeeded(
            challenge,
            purpose=VerificationPurpose.EMAIL,
        )
        user.mark_verified(challenge=challenge)
        self.verification_challenge_repository.save(challenge)
        self.account_repository.save(user)
        for event in challenge.pull_events():
            self.event_outbox.dispatch(event)
        for event in user.pull_events():
            self.event_outbox.dispatch(event)


__all__ = ["VerifyEmailUseCase"]
