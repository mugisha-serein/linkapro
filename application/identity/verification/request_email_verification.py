"""Request an email verification challenge."""

from typing import Protocol
import uuid

from application.identity.errors import UserNotFoundError
from application.identity.shared.ports import (
    AccountRepository,
    EmailVerificationSender,
    EventOutbox,
    VerificationChallengeRepository,
)
from domain.identity.verification import (
    EmailVerificationToken,
    VerificationCode,
    VerificationPolicy,
    VerificationPurpose,
)


class EmailVerificationTokenIssuer(Protocol):
    def create_email_verification_token(self, user_id: str, challenge_id: str) -> str:
        ...


class RequestEmailVerificationUseCase:
    def __init__(
        self,
        *,
        account_repository: AccountRepository,
        verification_challenge_repository: VerificationChallengeRepository,
        token_service: EmailVerificationTokenIssuer,
        email_verification_sender: EmailVerificationSender,
        event_outbox: EventOutbox,
        verification_policy: VerificationPolicy | None = None,
    ) -> None:
        self.account_repository = account_repository
        self.verification_challenge_repository = verification_challenge_repository
        self.token_service = token_service
        self.email_verification_sender = email_verification_sender
        self.event_outbox = event_outbox
        self.verification_policy = verification_policy or VerificationPolicy()

    def execute(self, *, user_id: uuid.UUID) -> EmailVerificationToken:
        user = self.account_repository.get_by_id(user_id)
        if not user:
            raise UserNotFoundError("User not found")

        challenge = self.verification_policy.issue_challenge(
            user_id=user.id,
            purpose=VerificationPurpose.EMAIL,
            code=VerificationCode(str(uuid.uuid4())),
        )
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


__all__ = ["EmailVerificationTokenIssuer", "RequestEmailVerificationUseCase"]
