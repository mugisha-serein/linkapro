import pyotp
import pytest
from django.contrib.auth.hashers import check_password
from django.test import override_settings

from application.identity.credentials import ChangePasswordUseCase, SetupPasswordUseCase
from application.identity.credentials.change_password_command import ChangePasswordCommand
from application.identity.credentials.setup_password_command import SetupPasswordCommand
from application.identity.mfa import (
    BeginMfaEnrollmentUseCase,
    ConfirmMfaEnrollmentUseCase,
    DisableMfaUseCase,
)
from application.identity.mfa.begin_mfa_enrollment_command import EnableTwoFactorCommand
from application.identity.mfa.confirm_mfa_enrollment_command import VerifyTwoFactorSetupCommand
from application.identity.mfa.disable_mfa_command import DisableMfaCommand
from application.identity.recovery.reset_password import ResetPasswordCommandHandler
from application.identity.recovery.reset_password_command import (
    PasswordResetTokenInput,
    ResetPasswordCommand,
    SecurityMetadataHash,
)
from application.identity.sessions import RevokeAllSessionsUseCase
from domain.identity.credentials import PlainPassword
from domain.identity.mfa import TOTPSecret
from domain.identity.verification import VerificationCode
from django_app.identity.models import IdentitySession, PasswordHistoryEntry, PasswordResetToken, User
from infrastructure.identity.clock import SystemClock
from infrastructure.identity.django_identity_session_store import DjangoIdentitySessionStore
from infrastructure.identity.django_mfa_challenge_store import (
    DjangoMfaEnrollmentStore,
    DjangoMfaReplayStore,
)
from infrastructure.identity.django_password_reset_gateway import DjangoPasswordResetGateway
from infrastructure.identity.django_unit_of_work import DjangoIdentityUnitOfWork
from infrastructure.identity.django_user_repository import DjangoUserRepository
from infrastructure.identity.jwt_token_service import JWTTokenService
from infrastructure.identity.pyotp_totp_service import PyotpTotpService
from infrastructure.identity.shared.security_primitives import DjangoPasswordHasher


pytestmark = pytest.mark.django_db(transaction=True)


class _KeyProvider:
    def wrap_dek(self, dek: bytes) -> bytes:
        return dek

    def unwrap_dek(self, encrypted_dek: bytes) -> bytes:
        return encrypted_dek


class FailingEventOutbox:
    def dispatch(self, event) -> None:
        raise RuntimeError("outbox unavailable")


class RecordingTokenFamilyRepository:
    def __init__(self):
        self.blacklisted = []

    def blacklist_family(self, family_id: str) -> None:
        self.blacklisted.append(family_id)


def _repo() -> DjangoUserRepository:
    return DjangoUserRepository(key_provider=_KeyProvider())


def _revoke_all_sessions_use_case(token_family_repository=None) -> RevokeAllSessionsUseCase:
    return RevokeAllSessionsUseCase(
        session_repository=DjangoIdentitySessionStore(),
        token_family_repository=token_family_repository or RecordingTokenFamilyRepository(),
    )


def _user(*, email: str, password: str | None = "CurrentPass1!", two_factor_enabled=False) -> User:
    user = User.objects.create_user(
        email=email,
        password=password,
        first_name="Rollback",
        last_name="User",
        role="planner",
        is_verified=True,
    )
    if password is None:
        user.set_unusable_password()
        user.save(update_fields=["password"])
    if two_factor_enabled:
        _repo().set_totp_secret(user.id, TOTPSecret("JBSWY3DPEHPK3PXP"))
    return User.objects.get(id=user.id)


def _active_session(user: User, token_family="family-one") -> IdentitySession:
    return IdentitySession.objects.create(user=user, token_family=token_family)


def test_change_password_rolls_back_hash_history_version_sessions_and_outbox_on_failure():
    user = _user(email="change-rollback@example.com")
    session = _active_session(user)
    original_password = user.password
    token_families = RecordingTokenFamilyRepository()

    with pytest.raises(RuntimeError, match="outbox unavailable"):
        ChangePasswordUseCase(
            account_repository=_repo(),
            password_hasher=DjangoPasswordHasher(),
            event_outbox=FailingEventOutbox(),
            revoke_all_sessions_use_case=_revoke_all_sessions_use_case(token_families),
            unit_of_work=DjangoIdentityUnitOfWork(),
        ).execute(
            ChangePasswordCommand(
                user_id=user.id,
                current_password=PlainPassword("CurrentPass1!"),
                new_password=PlainPassword("NextValidPass1!"),
            )
        )

    user.refresh_from_db()
    session.refresh_from_db()
    assert user.password == original_password
    assert check_password("CurrentPass1!", user.password)
    assert user.auth_token_version == 0
    assert PasswordHistoryEntry.objects.filter(user=user).count() == 0
    assert session.revoked_at is None


def test_setup_password_rolls_back_hash_history_version_sessions_and_outbox_on_failure():
    user = _user(email="setup-rollback@example.com", password=None)
    session = _active_session(user)

    with pytest.raises(RuntimeError, match="outbox unavailable"):
        SetupPasswordUseCase(
            account_repository=_repo(),
            password_hasher=DjangoPasswordHasher(),
            event_outbox=FailingEventOutbox(),
            revoke_all_sessions_use_case=_revoke_all_sessions_use_case(),
            unit_of_work=DjangoIdentityUnitOfWork(),
        ).execute(
            SetupPasswordCommand(
                user_id=user.id,
                plain_password=PlainPassword("SetupValidPass1!"),
            )
        )

    user.refresh_from_db()
    session.refresh_from_db()
    assert user.has_usable_password() is False
    assert user.auth_token_version == 0
    assert PasswordHistoryEntry.objects.filter(user=user).count() == 0
    assert session.revoked_at is None


@override_settings(MFA_REPLAY_HMAC_KEY="mfa-replay-test-key")
def test_confirm_mfa_enrollment_rolls_back_secret_flag_and_keeps_enrollment_on_failure():
    user = _user(email="mfa-confirm-rollback@example.com")
    enrollment_store = DjangoMfaEnrollmentStore()
    setup = BeginMfaEnrollmentUseCase(
        account_repository=_repo(),
        mfa_enrollment_repository=enrollment_store,
        totp_service=PyotpTotpService(),
    ).execute(EnableTwoFactorCommand(user_id=user.id))
    token = VerificationCode(pyotp.TOTP(setup.secret).now())

    with pytest.raises(RuntimeError, match="outbox unavailable"):
        ConfirmMfaEnrollmentUseCase(
            account_repository=_repo(),
            totp_secret_repository=_repo(),
            mfa_enrollment_repository=enrollment_store,
            mfa_replay_store=DjangoMfaReplayStore(),
            totp_service=PyotpTotpService(),
            event_outbox=FailingEventOutbox(),
            unit_of_work=DjangoIdentityUnitOfWork(),
        ).execute(VerifyTwoFactorSetupCommand(user_id=user.id, token=token))

    user.refresh_from_db()
    assert user.totp_secret is None
    assert user.two_factor_enabled is False
    assert user.auth_token_version == 0
    assert _repo().get_totp_secret(user.id) is None
    assert enrollment_store.get(user.id) is not None


def test_disable_mfa_rolls_back_secret_flag_and_account_version_on_failure():
    user = _user(email="mfa-disable-rollback@example.com", two_factor_enabled=True)
    original_secret = User.objects.get(id=user.id).totp_secret

    with pytest.raises(RuntimeError, match="outbox unavailable"):
        DisableMfaUseCase(
            account_repository=_repo(),
            totp_secret_repository=_repo(),
            event_outbox=FailingEventOutbox(),
            clock=SystemClock(),
            unit_of_work=DjangoIdentityUnitOfWork(),
        ).execute(DisableMfaCommand(user_id=user.id))

    user.refresh_from_db()
    assert user.totp_secret == original_secret
    assert user.two_factor_enabled is True
    assert user.auth_token_version == 0
    assert _repo().get_totp_secret(user.id).reveal_for_totp_verification() == "JBSWY3DPEHPK3PXP"


@override_settings(PASSWORD_RESET_HASH_KEY="password-reset-test-key")
def test_reset_password_rolls_back_hash_history_version_sessions_token_and_outbox_on_failure():
    user = _user(email="reset-rollback@example.com")
    session = _active_session(user)
    reset_token = JWTTokenService().issue_password_reset_token(user)
    token_record = PasswordResetToken.objects.get(user=user)
    original_password = user.password

    with pytest.raises(RuntimeError, match="outbox unavailable"):
        ResetPasswordCommandHandler(
            account_repository=_repo(),
            password_reset_repository=DjangoPasswordResetGateway(),
            password_history_repository=DjangoPasswordResetGateway(),
            password_hasher=DjangoPasswordHasher(),
            event_outbox=FailingEventOutbox(),
            revoke_all_sessions_use_case=_revoke_all_sessions_use_case(),
            unit_of_work=DjangoIdentityUnitOfWork(),
        ).handle(
            ResetPasswordCommand(
                token=PasswordResetTokenInput(reset_token),
                new_password=PlainPassword("ResetValidPass1!"),
                client_ip_hash=SecurityMetadataHash("a" * 64),
                user_agent_hash=SecurityMetadataHash("b" * 64),
            )
        )

    user.refresh_from_db()
    session.refresh_from_db()
    token_record.refresh_from_db()
    assert user.password == original_password
    assert check_password("CurrentPass1!", user.password)
    assert user.auth_token_version == 0
    assert PasswordHistoryEntry.objects.filter(user=user).count() == 0
    assert session.revoked_at is None
    assert token_record.status == PasswordResetToken.Status.ACTIVE
    assert token_record.used_at is None
