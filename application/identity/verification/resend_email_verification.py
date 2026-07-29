"""Resend an existing email verification challenge."""

import uuid

from application.identity.errors import UserNotFoundError
from application.identity.shared.ports import (
    AccountRepository,
    EmailVerificationSender,
    EventOutbox,
    VerificationChallengeRepository,
)
from application.identity.verification.request_email_verification import EmailVerificationTokenIssuer
from domain.identity.verification import EmailVerificationToken, VerificationResendPolicy


class ResendEmailVerificationUseCase:
    def __init__(
        self,
        *,
        account_repository: AccountRepository,
        verification_challenge_repository: VerificationChallengeRepository,
        token_service: EmailVerificationTokenIssuer,
        email_verification_sender: EmailVerificationSender,
        event_outbox: EventOutbox,
        resend_policy: VerificationResendPolicy | None = None,
    ) -> None:
        self.account_repository = account_repository
        self.verification_challenge_repository = verification_challenge_repository
        self.token_service = token_service
        self.email_verification_sender = email_verification_sender
        self.event_outbox = event_outbox
        self.resend_policy = resend_policy or VerificationResendPolicy()

    def execute(self, *, challenge_id: uuid.UUID) -> EmailVerificationToken:
        challenge = self.verification_challenge_repository.get(challenge_id)
        if not challenge:
            raise UserNotFoundError("Verification challenge not found")
        user = self.account_repository.get_by_id(challenge.user_id)
        if not user:
            raise UserNotFoundError("User not found")

        self.resend_policy.record_resend(challenge)
        self.verification_challenge_repository.save(challenge)
        token = EmailVerificationToken(
            self.token_service.create_email_verification_token(
                str(user.id),
                str(challenge.id),
            )
        )
        self.email_verification_sender.send_email_verification(
            to=str(user.email),
            token=token,
        )
        for event in challenge.pull_events():
            self.event_outbox.dispatch(event)
        return token


__all__ = ["ResendEmailVerificationUseCase"]
