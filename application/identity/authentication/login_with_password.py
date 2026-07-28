"""Authenticate an account with email and password."""

from typing import Protocol

from application.identity.auth_policy import AuthenticationDecision, AuthenticationStatus, IdentityAuthenticationPolicy
from application.identity.commands import LoginUserCommand
from application.identity.shared.ports import IUserRepository, PasswordHasher


class EventOutbox(Protocol):
    def dispatch(self, event) -> None:
        ...


class LoginWithPasswordUseCase:
    def __init__(
        self,
        *,
        account_repository: IUserRepository,
        password_hasher: PasswordHasher,
        auth_policy: IdentityAuthenticationPolicy,
        event_outbox: EventOutbox,
    ) -> None:
        self.account_repository = account_repository
        self.password_hasher = password_hasher
        self.auth_policy = auth_policy
        self.event_outbox = event_outbox

    def execute(self, cmd: LoginUserCommand) -> AuthenticationDecision:
        user = self.account_repository.get_by_email(cmd.email)
        if not user:
            self.password_hasher.verify_against_dummy(cmd.plain_password)
            return AuthenticationDecision(AuthenticationStatus.INVALID_CREDENTIALS)

        decision = self.auth_policy.evaluate_password_login(
            user=user,
            plain_password=cmd.plain_password,
            password_hasher=self.password_hasher,
        )
        if decision.status is not AuthenticationStatus.AUTHENTICATED:
            return decision

        user.record_login()
        self.account_repository.save(user)
        for event in user.pull_events():
            self.event_outbox.dispatch(event)

        return decision


__all__ = ["LoginWithPasswordUseCase"]
