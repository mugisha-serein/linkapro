"""Change an authenticated account password."""

from typing import Protocol

from application.identity.commands import ChangePasswordCommand
from application.identity.errors import InvalidCredentialsError, UserNotFoundError
from application.identity.shared.ports import IUserRepository, PasswordHasher
from domain.identity.credentials import PasswordHash, PasswordPolicy


class EventOutbox(Protocol):
    def dispatch(self, event) -> None:
        ...


class ChangePasswordUseCase:
    def __init__(
        self,
        *,
        account_repository: IUserRepository,
        password_hasher: PasswordHasher,
        event_outbox: EventOutbox,
    ) -> None:
        self.account_repository = account_repository
        self.password_hasher = password_hasher
        self.event_outbox = event_outbox

    def execute(self, cmd: ChangePasswordCommand) -> None:
        user = self.account_repository.get_by_id(cmd.user_id)
        if not user:
            raise UserNotFoundError("User not found")
        if not user.password_hash or not self.password_hasher.verify(
            cmd.current_password,
            user.password_hash,
        ):
            raise InvalidCredentialsError("Invalid credentials")

        PasswordPolicy.validate(cmd.new_password)
        password_history = self.account_repository.get_password_history(user.id)
        new_password_hash = PasswordHash(self.password_hasher.hash(cmd.new_password))
        user.change_password(
            new_password_hash,
            plain_password=cmd.new_password,
            password_history=password_history,
            password_verifier=self.password_hasher.verify,
        )
        self.account_repository.save(user)
        for event in user.pull_events():
            self.event_outbox.dispatch(event)


__all__ = ["ChangePasswordUseCase"]
