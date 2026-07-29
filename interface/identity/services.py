from infrastructure.identity.django_user_repository import DjangoUserRepository
from infrastructure.identity.django_oauth_token_repository import DjangoOAuthTokenRepository
from infrastructure.identity.shared.security_primitives import DjangoPasswordHasher
from infrastructure.identity.jwt_token_service import JWTTokenService
from infrastructure.identity.google_oauth_adapter import GoogleOAuthAdapter
from infrastructure.identity.django_identity_event_outbox import DjangoIdentityEventOutboxDispatcher
from infrastructure.identity.django_identity_session_store import DjangoIdentitySessionStore
from infrastructure.identity.django_mfa_challenge_store import (
    DjangoMfaChallengeRepository,
    DjangoMfaEnrollmentStore,
    DjangoMfaReplayStore,
)
from infrastructure.identity.django_mfa_recovery_codes import (
    DjangoMfaRecoveryCodeRepository,
    HmacRecoveryCodeHasher,
    SecureRecoveryCodeGenerator,
)
from infrastructure.identity.django_authentication_attempt_repository import DjangoAuthenticationAttemptRepository
from infrastructure.identity.django_verification_challenge_repository import DjangoVerificationChallengeRepository
from infrastructure.identity.email_verification_sender import DjangoEmailVerificationSender
from infrastructure.identity.pyotp_totp_service import PyotpTotpService
from infrastructure.identity.clock import SystemClock
from infrastructure.identity.id_generator import UuidGenerator
from infrastructure.identity.django_unit_of_work import DjangoIdentityUnitOfWork
from application.identity.account import (
    DeactivateAccountUseCase,
    RegisterAccountUseCase,
    UpdateAccountProfileUseCase,
)
from application.identity.authentication import (
    CompleteMfaLoginUseCase,
    LoginWithPasswordUseCase,
)
from application.identity.authorization import (
    AssignRoleUseCase,
    ReactivateAccountUseCase,
    SuspendAccountUseCase,
    UnlockAccountUseCase,
)
from application.identity.mfa import (
    BeginMfaEnrollmentUseCase,
    ConfirmMfaEnrollmentUseCase,
    ConsumeRecoveryCodeUseCase,
    DisableMfaUseCase,
    GenerateRecoveryCodesUseCase,
    RegenerateRecoveryCodesUseCase,
)
from application.identity.credentials import ChangePasswordUseCase, SetupPasswordUseCase
from application.identity.verification import (
    RequestEmailVerificationUseCase,
    ResendEmailVerificationUseCase,
    VerifyEmailUseCase,
)
from application.identity.authentication import AuthenticatedSessionIssuer
from application.identity.account_lockout import AccountLockoutConfig, AccountLockoutService
from application.identity.queries import GetAccountQueryUseCase
from application.identity.oauth import GoogleLoginUseCase
from application.identity.sessions import (
    IssueStepUpTokenUseCase,
    ListActiveSessionsUseCase,
    RefreshSessionUseCase,
    RevokeAllSessionsUseCase,
    RevokeCurrentSessionUseCase,
    RevokeOtherSessionsUseCase,
    RevokeSessionUseCase,
)
from application.identity.recovery import RequestPasswordResetUseCase
from application.identity.recovery.reset_password import ResetPasswordCommandHandler
from infrastructure.identity.shared.security_primitives import RedisTokenBlacklist
from infrastructure.identity.django_password_reset_gateway import DjangoPasswordResetGateway
from interface.identity.password_reset_request_gateway import DjangoPasswordResetRequestGateway
from django.conf import settings


class IdentityCommandFacade:
    def __init__(
        self,
        *,
        register_account_use_case,
        update_account_profile_use_case,
        deactivate_account_use_case,
        login_with_password_use_case,
        complete_mfa_login_use_case,
        begin_mfa_enrollment_use_case,
        confirm_mfa_enrollment_use_case,
        disable_mfa_use_case,
        verify_email_use_case,
        assign_role_use_case,
        suspend_account_use_case,
        reactivate_account_use_case,
        unlock_account_use_case,
    ) -> None:
        self.register_account_use_case = register_account_use_case
        self.update_account_profile_use_case = update_account_profile_use_case
        self.deactivate_account_use_case = deactivate_account_use_case
        self.login_with_password_use_case = login_with_password_use_case
        self.complete_mfa_login_use_case = complete_mfa_login_use_case
        self.begin_mfa_enrollment_use_case = begin_mfa_enrollment_use_case
        self.confirm_mfa_enrollment_use_case = confirm_mfa_enrollment_use_case
        self.disable_mfa_use_case = disable_mfa_use_case
        self.verify_email_use_case = verify_email_use_case
        self.assign_role_use_case = assign_role_use_case
        self.suspend_account_use_case = suspend_account_use_case
        self.reactivate_account_use_case = reactivate_account_use_case
        self.unlock_account_use_case = unlock_account_use_case

    def register_user(self, cmd):
        return self.register_account_use_case.execute(cmd)

    def login_user(self, cmd):
        return self.login_with_password_use_case.execute(cmd)

    def verify_email(self, cmd) -> None:
        self.verify_email_use_case.execute(cmd)

    def update_profile(self, cmd):
        return self.update_account_profile_use_case.execute(cmd)

    def deactivate_user(self, cmd) -> None:
        self.deactivate_account_use_case.execute(cmd)

    def enable_two_factor(self, cmd):
        return self.begin_mfa_enrollment_use_case.execute(cmd)

    def verify_two_factor_setup(self, cmd) -> None:
        self.confirm_mfa_enrollment_use_case.execute(cmd)

    def disable_mfa(self, cmd) -> None:
        self.disable_mfa_use_case.execute(cmd)

    def login_two_factor(self, cmd):
        return self.complete_mfa_login_use_case.execute(cmd)

    def assign_role(self, cmd) -> None:
        self.assign_role_use_case.execute(cmd)

    def suspend_account(self, cmd) -> None:
        self.suspend_account_use_case.execute(cmd)

    def reactivate_account(self, cmd) -> None:
        self.reactivate_account_use_case.execute(cmd)

    def unlock_account(self, cmd) -> None:
        self.unlock_account_use_case.execute(cmd)


def get_command_handlers():
    user_repo = DjangoUserRepository()
    password_hasher = DjangoPasswordHasher()
    token_service = JWTTokenService()
    session_store = DjangoIdentitySessionStore()
    event_outbox = DjangoIdentityEventOutboxDispatcher()
    mfa_challenge_repository = DjangoMfaChallengeRepository()
    session_issuer = AuthenticatedSessionIssuer(
        token_service,
        session_store,
        mfa_challenge_repository=mfa_challenge_repository,
    )
    token_blacklist = RedisTokenBlacklist()
    mfa_enrollment_store = DjangoMfaEnrollmentStore()
    mfa_replay_store = DjangoMfaReplayStore()
    recovery_code_repository = DjangoMfaRecoveryCodeRepository()
    recovery_code_hasher = HmacRecoveryCodeHasher()
    totp_service = PyotpTotpService()
    account_lockout_service = AccountLockoutService(
        repository=DjangoAuthenticationAttemptRepository(),
        config=_login_lockout_config(),
    )
    return IdentityCommandFacade(
        register_account_use_case=RegisterAccountUseCase(
            account_repository=user_repo,
            password_hasher=password_hasher,
            event_outbox=event_outbox,
            clock=SystemClock(),
            id_generator=UuidGenerator(),
            unit_of_work=DjangoIdentityUnitOfWork(),
        ),
        update_account_profile_use_case=UpdateAccountProfileUseCase(
            account_repository=user_repo,
        ),
        deactivate_account_use_case=DeactivateAccountUseCase(
            account_repository=user_repo,
            event_outbox=event_outbox,
            clock=SystemClock(),
            revoke_all_sessions_use_case=get_revoke_all_sessions_use_case(),
        ),
        login_with_password_use_case=LoginWithPasswordUseCase(
            account_repository=user_repo,
            password_hasher=password_hasher,
            event_outbox=event_outbox,
            account_lockout_service=account_lockout_service,
            session_issuer=session_issuer,
        ),
        complete_mfa_login_use_case=CompleteMfaLoginUseCase(
            account_repository=user_repo,
            totp_secret_repository=user_repo,
            token_service=token_service,
            token_blacklist=token_blacklist,
            mfa_challenge_repository=mfa_challenge_repository,
            mfa_replay_store=mfa_replay_store,
            totp_service=totp_service,
            consume_recovery_code_use_case=ConsumeRecoveryCodeUseCase(
                recovery_code_repository=recovery_code_repository,
                recovery_code_hasher=recovery_code_hasher,
                clock=SystemClock(),
            ),
            event_outbox=event_outbox,
            session_issuer=session_issuer,
        ),
        begin_mfa_enrollment_use_case=BeginMfaEnrollmentUseCase(
            account_repository=user_repo,
            mfa_enrollment_repository=mfa_enrollment_store,
            totp_service=totp_service,
        ),
        confirm_mfa_enrollment_use_case=ConfirmMfaEnrollmentUseCase(
            account_repository=user_repo,
            totp_secret_repository=user_repo,
            mfa_enrollment_repository=mfa_enrollment_store,
            mfa_replay_store=mfa_replay_store,
            totp_service=totp_service,
            event_outbox=event_outbox,
            unit_of_work=DjangoIdentityUnitOfWork(),
        ),
        disable_mfa_use_case=DisableMfaUseCase(
            account_repository=user_repo,
            totp_secret_repository=user_repo,
            event_outbox=event_outbox,
            clock=SystemClock(),
            unit_of_work=DjangoIdentityUnitOfWork(),
        ),
        verify_email_use_case=VerifyEmailUseCase(
            account_repository=user_repo,
            verification_challenge_repository=DjangoVerificationChallengeRepository(),
            token_service=token_service,
            event_outbox=event_outbox,
        ),
        assign_role_use_case=AssignRoleUseCase(
            account_repository=user_repo,
            event_outbox=event_outbox,
            clock=SystemClock(),
        ),
        suspend_account_use_case=SuspendAccountUseCase(
            account_repository=user_repo,
            event_outbox=event_outbox,
            clock=SystemClock(),
            revoke_all_sessions_use_case=get_revoke_all_sessions_use_case(),
        ),
        reactivate_account_use_case=ReactivateAccountUseCase(
            account_repository=user_repo,
            event_outbox=event_outbox,
            clock=SystemClock(),
        ),
        unlock_account_use_case=UnlockAccountUseCase(
            account_repository=user_repo,
            event_outbox=event_outbox,
            clock=SystemClock(),
        ),
    )


def _login_lockout_config() -> AccountLockoutConfig:
    lockout_seconds = int(getattr(settings, "LOGIN_FAILURE_LOCKOUT_SECONDS", 900))
    return AccountLockoutConfig(
        max_failures=int(getattr(settings, "LOGIN_FAILURE_LOCKOUT_THRESHOLD", 8)),
        observation_window_seconds=int(
            getattr(settings, "LOGIN_FAILURE_OBSERVATION_WINDOW_SECONDS", lockout_seconds)
        ),
        lock_duration_seconds=lockout_seconds,
    )

def get_query_handlers():
    return GetAccountQueryUseCase(
        account_repository=DjangoUserRepository(),
    )


def get_google_oauth_adapter() -> GoogleOAuthAdapter:
    return GoogleOAuthAdapter()


def get_google_login_use_case() -> GoogleLoginUseCase:
    return GoogleLoginUseCase(
        user_repo=DjangoUserRepository(),
        oauth_repo=DjangoOAuthTokenRepository(),
        token_service=JWTTokenService(),
        session_store=DjangoIdentitySessionStore(),
        clock=SystemClock(),
        id_generator=UuidGenerator(),
        mfa_challenge_repository=DjangoMfaChallengeRepository(),
        event_dispatcher=DjangoIdentityEventOutboxDispatcher(),
        unit_of_work=DjangoIdentityUnitOfWork(),
    )


def get_refresh_session_use_case() -> RefreshSessionUseCase:
    session_store = DjangoIdentitySessionStore()
    return RefreshSessionUseCase(
        blacklist=RedisTokenBlacklist(),
        session_repository=session_store,
        session_security_state_reader=session_store,
        session_bootstrap_reader=session_store,
        token_service=JWTTokenService(),
    )


def get_revoke_session_use_case() -> RevokeCurrentSessionUseCase:
    return RevokeCurrentSessionUseCase(
        blacklist=RedisTokenBlacklist(),
        session_repository=DjangoIdentitySessionStore(),
        token_service=JWTTokenService(),
    )


def get_issue_step_up_token_use_case() -> IssueStepUpTokenUseCase:
    return IssueStepUpTokenUseCase(
        token_service=JWTTokenService(),
    )


def get_reset_password_handler() -> ResetPasswordCommandHandler:
    reset_gateway = DjangoPasswordResetGateway()
    return ResetPasswordCommandHandler(
        account_repository=DjangoUserRepository(),
        password_reset_repository=reset_gateway,
        password_history_repository=reset_gateway,
        password_hasher=DjangoPasswordHasher(),
        event_outbox=DjangoIdentityEventOutboxDispatcher(),
        revoke_all_sessions_use_case=get_revoke_all_sessions_use_case(),
        unit_of_work=DjangoIdentityUnitOfWork(),
    )


def get_request_password_reset_use_case() -> RequestPasswordResetUseCase:
    return RequestPasswordResetUseCase(gateway=DjangoPasswordResetRequestGateway())


def get_request_email_verification_use_case() -> RequestEmailVerificationUseCase:
    return RequestEmailVerificationUseCase(
        account_repository=DjangoUserRepository(),
        verification_challenge_repository=DjangoVerificationChallengeRepository(),
        token_service=JWTTokenService(),
        email_verification_sender=DjangoEmailVerificationSender(),
        event_outbox=DjangoIdentityEventOutboxDispatcher(),
    )


def get_resend_email_verification_use_case() -> ResendEmailVerificationUseCase:
    return ResendEmailVerificationUseCase(
        account_repository=DjangoUserRepository(),
        verification_challenge_repository=DjangoVerificationChallengeRepository(),
        token_service=JWTTokenService(),
        email_verification_sender=DjangoEmailVerificationSender(),
        event_outbox=DjangoIdentityEventOutboxDispatcher(),
    )


def get_setup_password_use_case() -> SetupPasswordUseCase:
    return SetupPasswordUseCase(
        account_repository=DjangoUserRepository(),
        password_hasher=DjangoPasswordHasher(),
        event_outbox=DjangoIdentityEventOutboxDispatcher(),
        revoke_all_sessions_use_case=get_revoke_all_sessions_use_case(),
        unit_of_work=DjangoIdentityUnitOfWork(),
    )


def get_change_password_use_case() -> ChangePasswordUseCase:
    return ChangePasswordUseCase(
        account_repository=DjangoUserRepository(),
        password_hasher=DjangoPasswordHasher(),
        event_outbox=DjangoIdentityEventOutboxDispatcher(),
        revoke_all_sessions_use_case=get_revoke_all_sessions_use_case(),
        unit_of_work=DjangoIdentityUnitOfWork(),
    )


def get_generate_recovery_codes_use_case() -> GenerateRecoveryCodesUseCase:
    return GenerateRecoveryCodesUseCase(
        account_repository=DjangoUserRepository(),
        recovery_code_repository=DjangoMfaRecoveryCodeRepository(),
        recovery_code_generator=SecureRecoveryCodeGenerator(),
        recovery_code_hasher=HmacRecoveryCodeHasher(),
        id_generator=UuidGenerator(),
    )


def get_regenerate_recovery_codes_use_case() -> RegenerateRecoveryCodesUseCase:
    recovery_code_repository = DjangoMfaRecoveryCodeRepository()
    return RegenerateRecoveryCodesUseCase(
        recovery_code_repository=recovery_code_repository,
        generate_recovery_codes_use_case=GenerateRecoveryCodesUseCase(
            account_repository=DjangoUserRepository(),
            recovery_code_repository=recovery_code_repository,
            recovery_code_generator=SecureRecoveryCodeGenerator(),
            recovery_code_hasher=HmacRecoveryCodeHasher(),
            id_generator=UuidGenerator(),
        ),
    )


def get_disable_mfa_use_case() -> DisableMfaUseCase:
    return DisableMfaUseCase(
        account_repository=DjangoUserRepository(),
        totp_secret_repository=DjangoUserRepository(),
        event_outbox=DjangoIdentityEventOutboxDispatcher(),
        clock=SystemClock(),
        unit_of_work=DjangoIdentityUnitOfWork(),
    )


def get_revoke_all_sessions_use_case() -> RevokeAllSessionsUseCase:
    return RevokeAllSessionsUseCase(
        session_repository=DjangoIdentitySessionStore(),
        token_family_repository=RedisTokenBlacklist(),
    )


def get_list_active_sessions_use_case() -> ListActiveSessionsUseCase:
    return ListActiveSessionsUseCase(
        session_repository=DjangoIdentitySessionStore(),
    )


def get_revoke_named_session_use_case() -> RevokeSessionUseCase:
    return RevokeSessionUseCase(
        session_repository=DjangoIdentitySessionStore(),
        token_family_repository=RedisTokenBlacklist(),
    )


def get_revoke_other_sessions_use_case() -> RevokeOtherSessionsUseCase:
    return RevokeOtherSessionsUseCase(
        session_repository=DjangoIdentitySessionStore(),
        token_family_repository=RedisTokenBlacklist(),
    )


def get_assign_role_use_case() -> AssignRoleUseCase:
    return AssignRoleUseCase(
        account_repository=DjangoUserRepository(),
        event_outbox=DjangoIdentityEventOutboxDispatcher(),
        clock=SystemClock(),
    )


def get_suspend_account_use_case() -> SuspendAccountUseCase:
    return SuspendAccountUseCase(
        account_repository=DjangoUserRepository(),
        event_outbox=DjangoIdentityEventOutboxDispatcher(),
        clock=SystemClock(),
        revoke_all_sessions_use_case=get_revoke_all_sessions_use_case(),
    )


def get_reactivate_account_use_case() -> ReactivateAccountUseCase:
    return ReactivateAccountUseCase(
        account_repository=DjangoUserRepository(),
        event_outbox=DjangoIdentityEventOutboxDispatcher(),
        clock=SystemClock(),
    )


def get_unlock_account_use_case() -> UnlockAccountUseCase:
    return UnlockAccountUseCase(
        account_repository=DjangoUserRepository(),
        event_outbox=DjangoIdentityEventOutboxDispatcher(),
        clock=SystemClock(),
    )
