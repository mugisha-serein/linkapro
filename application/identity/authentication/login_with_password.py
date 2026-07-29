"""Authenticate an account with email and password."""

from .authenticated_session_issuer import AuthenticationDecision, AuthenticationStatus, AuthenticatedSessionIssuer
from application.identity.account_lockout import AccountLockoutService
from application.identity.authentication.login_with_password_command import LoginUserCommand
from application.identity.shared.ports import EventOutbox, AccountRepository, PasswordHasher


class LoginWithPasswordUseCase:
    def __init__(
        self,
        *,
        account_repository: AccountRepository,
        password_hasher: PasswordHasher,
        event_outbox: EventOutbox,
        account_lockout_service: AccountLockoutService,
        session_issuer: AuthenticatedSessionIssuer,
    ) -> None:
        self.account_repository = account_repository
        self.password_hasher = password_hasher
        self.session_issuer = session_issuer
        self.event_outbox = event_outbox
        self.account_lockout_service = account_lockout_service

    def execute(self, cmd: LoginUserCommand) -> AuthenticationDecision:
        account_key = str(cmd.email)
        if self.account_lockout_service.is_locked(account_key).locked:
            return AuthenticationDecision(AuthenticationStatus.LOCKED)

        user = self.account_repository.get_by_email(cmd.email)
        if not user:
            self.password_hasher.verify_against_dummy(cmd.plain_password)
            return self._record_invalid_credentials(account_key)

        decision = self.session_issuer.evaluate_password_login(
            user=user,
            plain_password=cmd.plain_password,
            password_hasher=self.password_hasher,
        )
        if decision.status is AuthenticationStatus.INVALID_CREDENTIALS:
            return self._record_invalid_credentials(account_key, user=user)
        if decision.status is AuthenticationStatus.MFA_REQUIRED:
            self.account_lockout_service.record_success(account_key)
            return decision
        if decision.status is not AuthenticationStatus.AUTHENTICATED:
            return decision

        self.account_lockout_service.record_success(account_key)
        user.record_login()
        self.account_repository.save(user)
        for event in user.pull_events():
            self.event_outbox.dispatch(event)

        return decision

    def _record_invalid_credentials(self, account_key: str, *, user=None) -> AuthenticationDecision:
        decision = self.account_lockout_service.record_failure(account_key)
        if decision.locked:
            return AuthenticationDecision(AuthenticationStatus.LOCKED, user=user)
        return AuthenticationDecision(AuthenticationStatus.INVALID_CREDENTIALS, user=user)


__all__ = ["LoginWithPasswordUseCase"]
