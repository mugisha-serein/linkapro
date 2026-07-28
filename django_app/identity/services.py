from infrastructure.identity.django_user_repository import DjangoUserRepository
from infrastructure.identity.django_oauth_token_repository import DjangoOAuthTokenRepository
from infrastructure.identity.shared.security_primitives import DjangoPasswordHasher
from infrastructure.identity.jwt_token_service import JWTTokenService
from infrastructure.identity.google_oauth_adapter import GoogleOAuthAdapter
from infrastructure.identity.django_identity_event_outbox import DjangoIdentityEventOutboxDispatcher
from infrastructure.identity.django_identity_session_store import DjangoIdentitySessionStore
from infrastructure.identity.django_mfa_challenge_store import DjangoMfaEnrollmentStore, DjangoMfaReplayStore
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
from application.identity.mfa import BeginMfaEnrollmentUseCase, ConfirmMfaEnrollmentUseCase, DisableMfaUseCase
from application.identity.credentials import ChangePasswordUseCase, SetupPasswordUseCase
from application.identity.verification import VerifyEmailUseCase
from application.identity.auth_policy import IdentityAuthenticationPolicy
from application.identity.queries import GetAccountQueryUseCase
from application.identity.use_cases.google_login import GoogleLoginUseCase
from application.identity.session_facade import IdentitySessionFacade
from application.identity.sessions import ListActiveSessionsUseCase, RevokeAllSessionsUseCase
from application.identity.token_handlers import TokenCommandHandlers
from application.identity.recovery import RequestPasswordResetUseCase, ResetPasswordCommandHandler
from infrastructure.identity.shared.security_primitives import RedisTokenBlacklist
from infrastructure.identity.django_password_reset_gateway import DjangoPasswordResetGateway
from infrastructure.identity.django_password_reset_request_gateway import DjangoPasswordResetRequestGateway


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
    auth_policy = IdentityAuthenticationPolicy(token_service, session_store)
    token_blacklist = RedisTokenBlacklist()
    mfa_enrollment_store = DjangoMfaEnrollmentStore()
    mfa_replay_store = DjangoMfaReplayStore()
    totp_service = PyotpTotpService()
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
        ),
        login_with_password_use_case=LoginWithPasswordUseCase(
            account_repository=user_repo,
            password_hasher=password_hasher,
            auth_policy=auth_policy,
            event_outbox=event_outbox,
        ),
        complete_mfa_login_use_case=CompleteMfaLoginUseCase(
            account_repository=user_repo,
            totp_secret_repository=user_repo,
            token_service=token_service,
            token_blacklist=token_blacklist,
            mfa_replay_store=mfa_replay_store,
            totp_service=totp_service,
            auth_policy=auth_policy,
            event_outbox=event_outbox,
        ),
        begin_mfa_enrollment_use_case=BeginMfaEnrollmentUseCase(
            account_repository=user_repo,
            mfa_enrollment_store=mfa_enrollment_store,
            totp_service=totp_service,
        ),
        confirm_mfa_enrollment_use_case=ConfirmMfaEnrollmentUseCase(
            account_repository=user_repo,
            totp_secret_repository=user_repo,
            mfa_enrollment_store=mfa_enrollment_store,
            mfa_replay_store=mfa_replay_store,
            totp_service=totp_service,
            event_outbox=event_outbox,
        ),
        disable_mfa_use_case=DisableMfaUseCase(
            account_repository=user_repo,
            totp_secret_repository=user_repo,
            event_outbox=event_outbox,
            clock=SystemClock(),
        ),
        verify_email_use_case=VerifyEmailUseCase(
            account_repository=user_repo,
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
        event_dispatcher=DjangoIdentityEventOutboxDispatcher(),
        unit_of_work=DjangoIdentityUnitOfWork(),
    )


def get_token_handlers() -> TokenCommandHandlers:
    return TokenCommandHandlers(
        blacklist=RedisTokenBlacklist(),
        session_store=DjangoIdentitySessionStore(),
        token_service=JWTTokenService(),
    )


def get_auth_session_facade() -> IdentitySessionFacade:
    command_handlers = get_command_handlers()
    return IdentitySessionFacade(
        command_handlers=command_handlers,
        google_login_use_case=get_google_login_use_case(),
        token_handlers=get_token_handlers(),
    )


def get_reset_password_handler() -> ResetPasswordCommandHandler:
    return ResetPasswordCommandHandler(gateway=DjangoPasswordResetGateway())


def get_request_password_reset_use_case() -> RequestPasswordResetUseCase:
    return RequestPasswordResetUseCase(gateway=DjangoPasswordResetRequestGateway())


def get_setup_password_use_case() -> SetupPasswordUseCase:
    return SetupPasswordUseCase(
        account_repository=DjangoUserRepository(),
        password_hasher=DjangoPasswordHasher(),
        event_outbox=DjangoIdentityEventOutboxDispatcher(),
    )


def get_change_password_use_case() -> ChangePasswordUseCase:
    return ChangePasswordUseCase(
        account_repository=DjangoUserRepository(),
        password_hasher=DjangoPasswordHasher(),
        event_outbox=DjangoIdentityEventOutboxDispatcher(),
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
