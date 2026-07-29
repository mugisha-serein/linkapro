import uuid
from datetime import UTC, datetime
import hashlib
from unittest.mock import ANY, Mock

import pytest
import pyotp

from application.identity.mfa.begin_mfa_enrollment_command import EnableTwoFactorCommand
from application.identity.mfa.confirm_mfa_enrollment_command import VerifyTwoFactorSetupCommand
from application.identity.mfa.disable_mfa_command import DisableMfaCommand
from application.identity.errors import InvalidTwoFactorCodeError
from application.identity.mfa import (
    BeginMfaEnrollmentUseCase,
    ConsumeRecoveryCodeCommand,
    ConsumeRecoveryCodeUseCase,
    ConfirmMfaEnrollmentUseCase,
    DisableMfaUseCase,
    GenerateRecoveryCodesCommand,
    GenerateRecoveryCodesUseCase,
    RegenerateRecoveryCodesCommand,
    RegenerateRecoveryCodesUseCase,
)
from application.identity.shared.ports import MfaEnrollmentState
from domain.identity.account import User, UserRole
from domain.identity.credentials import Email, PasswordHash
from domain.identity.mfa import MfaPolicy, RecoveryCode, UserTwoFactorDisabled, UserTwoFactorEnabled
from domain.identity.verification import VerificationCode


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


class SequentialIdGenerator:
    def __init__(self):
        self.index = 1

    def new_id(self):
        value = uuid.UUID(int=self.index)
        self.index += 1
        return value


class SequentialRecoveryCodeGenerator:
    def __init__(self, codes):
        self.codes = list(codes)

    def generate(self):
        return self.codes.pop(0)


class PrefixRecoveryCodeHasher:
    def hash_recovery_code(self, code: str) -> str:
        return hashlib.sha256(code.encode("utf-8")).hexdigest()


class MemoryRecoveryCodeRepository:
    def __init__(self):
        self.by_user = {}
        self.cleared = []

    def get_for_user(self, user_id):
        return self.by_user.get(user_id, ())

    def save_for_user(self, user_id, recovery_codes):
        self.by_user[user_id] = recovery_codes

    def replace_for_user(self, user_id, recovery_codes):
        self.by_user[user_id] = recovery_codes

    def clear_for_user(self, user_id):
        self.cleared.append(user_id)
        self.by_user.pop(user_id, None)


def _user(*, two_factor_enabled=False):
    return User(
        id=uuid.uuid4(),
        email=Email("mfa@example.com"),
        password_hash=PasswordHash("hash"),
        first_name="MFA",
        last_name="User",
        role=UserRole.PLANNER,
        two_factor_enabled=two_factor_enabled,
    )


def _totp_service(secret: str | None = None):
    service = Mock()
    service.generate_secret.return_value = secret or pyotp.random_base32()
    service.provisioning_uri.side_effect = (
        lambda generated_secret, *, name, issuer_name: pyotp.TOTP(generated_secret).provisioning_uri(
            name=name,
            issuer_name=issuer_name,
        )
    )
    service.verify.side_effect = (
        lambda totp_secret, token, *, now: pyotp.TOTP(
            totp_secret.reveal_for_totp_verification()
        ).verify(token.value, for_time=now)
    )
    return service


def test_begin_mfa_enrollment_stores_challenge_state_and_returns_setup_dto():
    user = _user()
    secret = pyotp.random_base32()
    account_repository = Mock()
    account_repository.get_by_id.return_value = user
    mfa_enrollment_store = Mock()

    result = BeginMfaEnrollmentUseCase(
        account_repository=account_repository,
        mfa_enrollment_repository=mfa_enrollment_store,
        totp_service=_totp_service(secret),
    ).execute(EnableTwoFactorCommand(user_id=user.id))

    assert result.secret == secret
    assert result.enrollment_id
    mfa_enrollment_store.save.assert_called_once()
    saved_state = mfa_enrollment_store.save.call_args.args[0]
    assert isinstance(saved_state, MfaEnrollmentState)
    assert saved_state.challenge.user_id == user.id
    assert saved_state.secret == secret
    assert mfa_enrollment_store.save.call_args.kwargs["ttl"] == 600


def test_confirm_mfa_enrollment_enables_user_and_consumes_setup():
    user = _user()
    secret = pyotp.random_base32()
    token = VerificationCode(pyotp.TOTP(secret).now())
    account_repository = Mock()
    account_repository.get_by_id.return_value = user
    totp_secret_repository = Mock()
    mfa_enrollment_store = Mock()
    BeginMfaEnrollmentUseCase(
        account_repository=account_repository,
        mfa_enrollment_repository=mfa_enrollment_store,
        totp_service=_totp_service(secret),
    ).execute(EnableTwoFactorCommand(user_id=user.id))
    mfa_enrollment_store.get.return_value = mfa_enrollment_store.save.call_args.args[0]
    mfa_enrollment_store.reset_mock()
    mfa_replay_store = Mock()
    mfa_replay_store.has_been_used.return_value = False
    event_outbox = Mock()
    unit_of_work = RecordingUnitOfWork()

    ConfirmMfaEnrollmentUseCase(
        account_repository=account_repository,
        totp_secret_repository=totp_secret_repository,
        mfa_enrollment_repository=mfa_enrollment_store,
        mfa_replay_store=mfa_replay_store,
        totp_service=_totp_service(),
        event_outbox=event_outbox,
        unit_of_work=unit_of_work,
    ).execute(VerifyTwoFactorSetupCommand(user_id=user.id, token=token))

    assert user.two_factor_enabled is True
    totp_secret_repository.set_totp_secret.assert_called_once()
    mfa_replay_store.has_been_used.assert_called_once_with(ANY, token)
    replay_ttl = mfa_replay_store.mark_used.call_args.kwargs["ttl"]
    assert 1 <= replay_ttl <= MfaPolicy().challenge_ttl_seconds()
    mfa_enrollment_store.consume.assert_called_once_with(user.id)
    account_repository.save.assert_called_once_with(user)
    event = event_outbox.dispatch.call_args.args[0]
    assert isinstance(event, UserTwoFactorEnabled)
    assert unit_of_work.entered is True
    assert unit_of_work.committed is True
    assert unit_of_work.rolled_back is False


def test_confirm_mfa_enrollment_rejects_replayed_token():
    user = _user()
    secret = pyotp.random_base32()
    token = VerificationCode(pyotp.TOTP(secret).now())
    account_repository = Mock()
    account_repository.get_by_id.return_value = user
    mfa_enrollment_store = Mock()
    BeginMfaEnrollmentUseCase(
        account_repository=account_repository,
        mfa_enrollment_repository=mfa_enrollment_store,
        totp_service=_totp_service(secret),
    ).execute(EnableTwoFactorCommand(user_id=user.id))
    mfa_enrollment_store.get.return_value = mfa_enrollment_store.save.call_args.args[0]
    mfa_enrollment_store.reset_mock()
    mfa_replay_store = Mock()
    mfa_replay_store.has_been_used.return_value = True
    event_outbox = Mock()
    unit_of_work = RecordingUnitOfWork()

    with pytest.raises(InvalidTwoFactorCodeError, match="Invalid TOTP token"):
        ConfirmMfaEnrollmentUseCase(
            account_repository=account_repository,
            totp_secret_repository=Mock(),
            mfa_enrollment_repository=mfa_enrollment_store,
            mfa_replay_store=mfa_replay_store,
            totp_service=_totp_service(),
            event_outbox=event_outbox,
            unit_of_work=unit_of_work,
        ).execute(VerifyTwoFactorSetupCommand(user_id=user.id, token=token))

    mfa_replay_store.mark_used.assert_not_called()
    event_outbox.dispatch.assert_not_called()
    assert unit_of_work.entered is False


def test_confirm_mfa_enrollment_rolls_back_unit_of_work_when_event_dispatch_fails():
    user = _user()
    secret = pyotp.random_base32()
    token = VerificationCode(pyotp.TOTP(secret).now())
    account_repository = Mock()
    account_repository.get_by_id.return_value = user
    totp_secret_repository = Mock()
    mfa_enrollment_store = Mock()
    BeginMfaEnrollmentUseCase(
        account_repository=account_repository,
        mfa_enrollment_repository=mfa_enrollment_store,
        totp_service=_totp_service(secret),
    ).execute(EnableTwoFactorCommand(user_id=user.id))
    mfa_enrollment_store.get.return_value = mfa_enrollment_store.save.call_args.args[0]
    mfa_enrollment_store.reset_mock()
    mfa_replay_store = Mock()
    mfa_replay_store.has_been_used.return_value = False
    event_outbox = Mock()
    event_outbox.dispatch.side_effect = RuntimeError("outbox unavailable")
    unit_of_work = RecordingUnitOfWork()

    with pytest.raises(RuntimeError, match="outbox unavailable"):
        ConfirmMfaEnrollmentUseCase(
            account_repository=account_repository,
            totp_secret_repository=totp_secret_repository,
            mfa_enrollment_repository=mfa_enrollment_store,
            mfa_replay_store=mfa_replay_store,
            totp_service=_totp_service(),
            event_outbox=event_outbox,
            unit_of_work=unit_of_work,
        ).execute(VerifyTwoFactorSetupCommand(user_id=user.id, token=token))

    assert unit_of_work.entered is True
    assert unit_of_work.committed is False
    assert unit_of_work.rolled_back is True


def test_disable_mfa_clears_secret_and_records_event():
    user = _user(two_factor_enabled=True)
    account_repository = Mock()
    account_repository.get_by_id.return_value = user
    totp_secret_repository = Mock()
    event_outbox = Mock()
    unit_of_work = RecordingUnitOfWork()

    DisableMfaUseCase(
        account_repository=account_repository,
        totp_secret_repository=totp_secret_repository,
        event_outbox=event_outbox,
        clock=FixedClock(),
        unit_of_work=unit_of_work,
    ).execute(DisableMfaCommand(user_id=user.id))

    assert user.two_factor_enabled is False
    totp_secret_repository.clear_totp_secret.assert_called_once_with(user.id)
    account_repository.save.assert_called_once_with(user)
    event = event_outbox.dispatch.call_args.args[0]
    assert isinstance(event, UserTwoFactorDisabled)
    assert event.occurred_at == datetime(2026, 1, 1, tzinfo=UTC)
    assert unit_of_work.entered is True
    assert unit_of_work.committed is True
    assert unit_of_work.rolled_back is False


def test_disable_mfa_rolls_back_unit_of_work_when_event_dispatch_fails():
    user = _user(two_factor_enabled=True)
    account_repository = Mock()
    account_repository.get_by_id.return_value = user
    event_outbox = Mock()
    event_outbox.dispatch.side_effect = RuntimeError("outbox unavailable")
    unit_of_work = RecordingUnitOfWork()

    with pytest.raises(RuntimeError, match="outbox unavailable"):
        DisableMfaUseCase(
            account_repository=account_repository,
            totp_secret_repository=Mock(),
            event_outbox=event_outbox,
            clock=FixedClock(),
            unit_of_work=unit_of_work,
        ).execute(DisableMfaCommand(user_id=user.id))

    assert unit_of_work.entered is True
    assert unit_of_work.committed is False
    assert unit_of_work.rolled_back is True


def test_generate_recovery_codes_persists_only_hashes_and_returns_plaintext_once():
    user = _user(two_factor_enabled=True)
    account_repository = Mock()
    account_repository.get_by_id.return_value = user
    recovery_code_repository = MemoryRecoveryCodeRepository()

    plaintext_codes = GenerateRecoveryCodesUseCase(
        account_repository=account_repository,
        recovery_code_repository=recovery_code_repository,
        recovery_code_generator=SequentialRecoveryCodeGenerator(["code-one", "code-two"]),
        recovery_code_hasher=PrefixRecoveryCodeHasher(),
        id_generator=SequentialIdGenerator(),
    ).execute(GenerateRecoveryCodesCommand(user_id=user.id, count=2))

    persisted = recovery_code_repository.get_for_user(user.id)
    assert plaintext_codes == ("code-one", "code-two")
    assert all(isinstance(code, RecoveryCode) for code in persisted)
    assert [code.code_hash for code in persisted] == [
        hashlib.sha256(b"code-one").hexdigest(),
        hashlib.sha256(b"code-two").hexdigest(),
    ]
    assert "code-one" not in repr(persisted)
    assert "code-two" not in repr(persisted)


def test_consume_recovery_code_marks_only_matching_code_used_once():
    user = _user(two_factor_enabled=True)
    recovery_code_repository = MemoryRecoveryCodeRepository()
    recovery_code_repository.replace_for_user(
        user.id,
        (
            RecoveryCode(id=uuid.UUID(int=1), code_hash=hashlib.sha256(b"valid-code").hexdigest()),
            RecoveryCode(id=uuid.UUID(int=2), code_hash=hashlib.sha256(b"other-code").hexdigest()),
        ),
    )
    use_case = ConsumeRecoveryCodeUseCase(
        recovery_code_repository=recovery_code_repository,
        recovery_code_hasher=PrefixRecoveryCodeHasher(),
        clock=FixedClock(),
    )

    first = use_case.execute(
        ConsumeRecoveryCodeCommand(user_id=user.id, code=VerificationCode("valid-code"))
    )
    second = use_case.execute(
        ConsumeRecoveryCodeCommand(user_id=user.id, code=VerificationCode("valid-code"))
    )

    persisted = recovery_code_repository.get_for_user(user.id)
    assert first is True
    assert second is False
    assert persisted[0].used_at == datetime(2026, 1, 1, tzinfo=UTC)
    assert persisted[1].used_at is None


def test_regenerate_recovery_codes_invalidates_old_codes_before_replacing():
    user = _user(two_factor_enabled=True)
    account_repository = Mock()
    account_repository.get_by_id.return_value = user
    recovery_code_repository = MemoryRecoveryCodeRepository()
    recovery_code_repository.replace_for_user(
        user.id,
        (RecoveryCode(id=uuid.UUID(int=1), code_hash=hashlib.sha256(b"old-code").hexdigest()),),
    )
    generate_use_case = GenerateRecoveryCodesUseCase(
        account_repository=account_repository,
        recovery_code_repository=recovery_code_repository,
        recovery_code_generator=SequentialRecoveryCodeGenerator(["new-code"]),
        recovery_code_hasher=PrefixRecoveryCodeHasher(),
        id_generator=SequentialIdGenerator(),
    )

    plaintext_codes = RegenerateRecoveryCodesUseCase(
        recovery_code_repository=recovery_code_repository,
        generate_recovery_codes_use_case=generate_use_case,
    ).execute(RegenerateRecoveryCodesCommand(user_id=user.id, count=1))

    persisted = recovery_code_repository.get_for_user(user.id)
    assert plaintext_codes == ("new-code",)
    assert recovery_code_repository.cleared == [user.id]
    assert [code.code_hash for code in persisted] == [hashlib.sha256(b"new-code").hexdigest()]
