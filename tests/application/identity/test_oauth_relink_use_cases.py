from datetime import UTC, datetime, timedelta
import uuid
from unittest.mock import Mock

import pytest

from application.identity.errors import OAuthRelinkRequiresStepUp
from application.identity.oauth import ConfirmOAuthRelinkCommand, ConfirmOAuthRelinkUseCase
from application.identity.oauth.confirm_oauth_relink import OAUTH_RELINK_STEP_UP_PURPOSE
from domain.identity.account import User, UserRole
from domain.identity.credentials import Email
from domain.identity.oauth import OAuthProvider, OAuthToken, UserOAuthLinked
from domain.shared.utils import utc_now


class FixedClock:
    def now(self):
        return datetime(2026, 1, 1, tzinfo=UTC)


class RecordingUnitOfWork:
    def __init__(self):
        self.entered = False
        self.committed = False
        self.rolled_back = False

    def __enter__(self):
        self.entered = True
        return self

    def __exit__(self, exc_type, exc, traceback):
        if exc_type is not None or not self.committed:
            self.rolled_back = True
        return None

    def commit(self):
        self.committed = True

    def rollback(self):
        self.rolled_back = True


def _target_account() -> User:
    return User(
        id=uuid.uuid4(),
        email=Email("target@example.com"),
        password_hash=None,
        first_name="Target",
        last_name="Account",
        role=UserRole.PLANNER,
        is_verified=True,
    )


def _oauth_identity(owner_id: uuid.UUID) -> OAuthToken:
    return OAuthToken(
        id=uuid.uuid4(),
        user_id=owner_id,
        provider=OAuthProvider.GOOGLE,
        provider_user_id="google-owned-elsewhere",
        access_token="old-access-token",
        refresh_token=None,
        expires_at=utc_now() + timedelta(hours=1),
    )


def _use_case(*, account, oauth_identity, grant_valid=True, unit_of_work=None):
    account_repository = Mock()
    account_repository.get_by_id.return_value = account
    oauth_repository = Mock()
    oauth_repository.get_by_provider_and_user.return_value = oauth_identity
    oauth_repository.get_by_user_and_provider.return_value = None
    step_up_grant_verifier = Mock()
    step_up_grant_verifier.verify.return_value = grant_valid
    event_outbox = Mock()
    use_case = ConfirmOAuthRelinkUseCase(
        account_repository=account_repository,
        oauth_repository=oauth_repository,
        step_up_grant_verifier=step_up_grant_verifier,
        event_outbox=event_outbox,
        clock=FixedClock(),
        unit_of_work=unit_of_work,
    )
    return use_case, account_repository, oauth_repository, step_up_grant_verifier, event_outbox


def test_confirm_oauth_relink_requires_valid_step_up_grant():
    account = _target_account()
    oauth_identity = _oauth_identity(owner_id=uuid.uuid4())
    use_case, account_repository, oauth_repository, step_up_grant_verifier, event_outbox = _use_case(
        account=account,
        oauth_identity=oauth_identity,
        grant_valid=False,
    )

    with pytest.raises(OAuthRelinkRequiresStepUp, match="step-up"):
        use_case.execute(
            ConfirmOAuthRelinkCommand(
                target_user_id=account.id,
                provider=OAuthProvider.GOOGLE,
                provider_user_id=oauth_identity.provider_user_id,
                step_up_grant="invalid-grant",
                provider_email_verified=True,
            )
        )

    assert oauth_identity.user_id != account.id
    step_up_grant_verifier.verify.assert_called_once_with(
        "invalid-grant",
        user_id=account.id,
        purpose=OAUTH_RELINK_STEP_UP_PURPOSE,
    )
    step_up_grant_verifier.consume.assert_not_called()
    account_repository.save.assert_not_called()
    oauth_repository.save.assert_not_called()
    event_outbox.dispatch.assert_not_called()


def test_confirm_oauth_relink_persists_binding_and_dispatches_after_step_up():
    account = _target_account()
    oauth_identity = _oauth_identity(owner_id=uuid.uuid4())
    unit_of_work = RecordingUnitOfWork()
    use_case, account_repository, oauth_repository, step_up_grant_verifier, event_outbox = _use_case(
        account=account,
        oauth_identity=oauth_identity,
        grant_valid=True,
        unit_of_work=unit_of_work,
    )

    use_case.execute(
        ConfirmOAuthRelinkCommand(
            target_user_id=account.id,
            provider=OAuthProvider.GOOGLE,
            provider_user_id=oauth_identity.provider_user_id,
            step_up_grant="valid-grant",
            provider_email_verified=True,
        )
    )

    assert oauth_identity.user_id == account.id
    account_repository.save.assert_called_once_with(account)
    oauth_repository.save.assert_called_once_with(oauth_identity)
    step_up_grant_verifier.consume.assert_called_once_with(
        "valid-grant",
        user_id=account.id,
        purpose=OAUTH_RELINK_STEP_UP_PURPOSE,
    )
    dispatched_event = event_outbox.dispatch.call_args.args[0]
    assert isinstance(dispatched_event, UserOAuthLinked)
    assert unit_of_work.entered is True
    assert unit_of_work.committed is True
    assert unit_of_work.rolled_back is False
