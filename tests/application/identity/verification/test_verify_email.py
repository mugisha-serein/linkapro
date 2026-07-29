import uuid
from unittest.mock import Mock

import pytest

from application.identity.verification.verify_email_command import VerifyEmailCommand
from application.identity.errors import InvalidCredentialsError, UserNotFoundError
from application.identity.verification import VerifyEmailUseCase
from domain.identity.account import User, UserRole
from domain.identity.credentials import Email, PasswordHash
from domain.identity.verification import (
    EmailVerificationToken,
    UserVerified,
    VerificationCode,
    VerificationPolicy,
    VerificationPurpose,
    VerificationChallengeSucceeded,
)


def test_verify_email_marks_user_verified_and_dispatches_events():
    user = User(
        id=uuid.uuid4(),
        email=Email("verify@example.com"),
        password_hash=PasswordHash("hash"),
        first_name="Verify",
        last_name="User",
        role=UserRole.PLANNER,
        is_active=True,
        is_verified=False,
    )
    account_repository = Mock()
    account_repository.get_by_id.return_value = user
    challenge = VerificationPolicy().issue_challenge(
        user_id=user.id,
        purpose=VerificationPurpose.EMAIL,
        code=VerificationCode("stored-code"),
    )
    challenge.pull_events()
    verification_challenge_repository = Mock()
    verification_challenge_repository.get.return_value = challenge
    token_service = Mock()
    token_service.verify_email_verification_token.return_value = str(challenge.id)
    event_outbox = Mock()

    VerifyEmailUseCase(
        account_repository=account_repository,
        verification_challenge_repository=verification_challenge_repository,
        token_service=token_service,
        event_outbox=event_outbox,
    ).execute(VerifyEmailCommand(verification_token=EmailVerificationToken("email-token")))

    assert user.is_verified is True
    verification_challenge_repository.save.assert_called_once_with(challenge)
    account_repository.save.assert_called_once_with(user)
    dispatched = [call.args[0] for call in event_outbox.dispatch.call_args_list]
    assert any(isinstance(event, VerificationChallengeSucceeded) for event in dispatched)
    assert any(isinstance(event, UserVerified) for event in dispatched)


def test_verify_email_rejects_invalid_token():
    token_service = Mock()
    token_service.verify_email_verification_token.return_value = None
    account_repository = Mock()
    verification_challenge_repository = Mock()
    event_outbox = Mock()

    with pytest.raises(InvalidCredentialsError, match="Invalid or expired verification token"):
        VerifyEmailUseCase(
            account_repository=account_repository,
            verification_challenge_repository=verification_challenge_repository,
            token_service=token_service,
            event_outbox=event_outbox,
        ).execute(VerifyEmailCommand(verification_token=EmailVerificationToken("bad-token")))

    account_repository.get_by_id.assert_not_called()
    verification_challenge_repository.get.assert_not_called()
    event_outbox.dispatch.assert_not_called()


def test_verify_email_missing_user_raises_typed_error():
    token_service = Mock()
    challenge = VerificationPolicy().issue_challenge(
        user_id=uuid.uuid4(),
        purpose=VerificationPurpose.EMAIL,
        code=VerificationCode("stored-code"),
    )
    challenge.pull_events()
    token_service.verify_email_verification_token.return_value = str(challenge.id)
    verification_challenge_repository = Mock()
    verification_challenge_repository.get.return_value = challenge
    account_repository = Mock()
    account_repository.get_by_id.return_value = None
    event_outbox = Mock()

    with pytest.raises(UserNotFoundError, match="User not found"):
        VerifyEmailUseCase(
            account_repository=account_repository,
            verification_challenge_repository=verification_challenge_repository,
            token_service=token_service,
            event_outbox=event_outbox,
        ).execute(VerifyEmailCommand(verification_token=EmailVerificationToken("email-token")))

    account_repository.save.assert_not_called()
    event_outbox.dispatch.assert_not_called()
