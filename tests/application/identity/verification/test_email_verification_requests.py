import uuid
from datetime import timedelta
from unittest.mock import Mock

import pytest

from application.identity.verification import (
    RequestEmailVerificationUseCase,
    ResendEmailVerificationUseCase,
)
from domain.identity.account import User, UserRole
from domain.identity.credentials import Email, PasswordHash
from domain.identity.verification import (
    VerificationCode,
    VerificationChallengeIssued,
    VerificationChallengeResent,
    VerificationPolicy,
    VerificationResendPolicy,
    VerificationResendTooSoon,
)


def _user() -> User:
    return User(
        id=uuid.uuid4(),
        email=Email("verify@example.com"),
        password_hash=PasswordHash("hash"),
        first_name="Verify",
        last_name="User",
        role=UserRole.PLANNER,
        is_active=True,
        is_verified=False,
    )


def test_request_email_verification_persists_challenge_and_sends_signed_token():
    user = _user()
    account_repository = Mock()
    account_repository.get_by_id.return_value = user
    challenge_repository = Mock()
    token_service = Mock()
    token_service.create_email_verification_token.return_value = "signed-token"
    sender = Mock()
    event_outbox = Mock()

    token = RequestEmailVerificationUseCase(
        account_repository=account_repository,
        verification_challenge_repository=challenge_repository,
        token_service=token_service,
        email_verification_sender=sender,
        event_outbox=event_outbox,
    ).execute(user_id=user.id)

    challenge = challenge_repository.save.call_args.args[0]
    token_service.create_email_verification_token.assert_called_once_with(
        str(user.id),
        str(challenge.id),
    )
    sender.send_email_verification.assert_called_once_with(
        to="verify@example.com",
        token=token,
    )
    dispatched = [call.args[0] for call in event_outbox.dispatch.call_args_list]
    assert any(isinstance(event, VerificationChallengeIssued) for event in dispatched)


def test_resend_email_verification_respects_cooldown():
    user = _user()
    challenge = VerificationPolicy(
        resend_cooldown=timedelta(minutes=10),
    ).issue_challenge(
        user_id=user.id,
        purpose="email",
        code=VerificationCode("code"),
    )
    challenge.pull_events()
    account_repository = Mock()
    account_repository.get_by_id.return_value = user
    challenge_repository = Mock()
    challenge_repository.get.return_value = challenge

    with pytest.raises(VerificationResendTooSoon):
        ResendEmailVerificationUseCase(
            account_repository=account_repository,
            verification_challenge_repository=challenge_repository,
            token_service=Mock(),
            email_verification_sender=Mock(),
            event_outbox=Mock(),
        ).execute(challenge_id=challenge.id)


def test_resend_email_verification_persists_resend_and_sends_token():
    user = _user()
    policy = VerificationPolicy(resend_cooldown=timedelta(seconds=0))
    challenge = policy.issue_challenge(
        user_id=user.id,
        purpose="email",
        code=VerificationCode("code"),
    )
    challenge.pull_events()
    account_repository = Mock()
    account_repository.get_by_id.return_value = user
    challenge_repository = Mock()
    challenge_repository.get.return_value = challenge
    token_service = Mock()
    token_service.create_email_verification_token.return_value = "signed-token"
    sender = Mock()
    event_outbox = Mock()

    ResendEmailVerificationUseCase(
        account_repository=account_repository,
        verification_challenge_repository=challenge_repository,
        token_service=token_service,
        email_verification_sender=sender,
        event_outbox=event_outbox,
        resend_policy=VerificationResendPolicy(cooldown=timedelta(seconds=0)),
    ).execute(challenge_id=challenge.id)

    challenge_repository.save.assert_called_once_with(challenge)
    token_service.create_email_verification_token.assert_called_once_with(
        str(user.id),
        str(challenge.id),
    )
    sender.send_email_verification.assert_called_once()
    dispatched = [call.args[0] for call in event_outbox.dispatch.call_args_list]
    assert any(isinstance(event, VerificationChallengeResent) for event in dispatched)
