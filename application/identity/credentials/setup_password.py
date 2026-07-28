"""Set an initial password for an account."""

from typing import Protocol

from application.identity.commands import SetupPasswordCommand
from application.identity.dtos import UserDTO
from application.identity.errors import UserNotFoundError
from application.identity.shared.mappers import to_user_dto
from application.identity.shared.ports import IUserRepository, PasswordHasher
from domain.identity.credentials import PasswordHash, PasswordPolicy


class EventOutbox(Protocol):
    def dispatch(self, event) -> None:
        ...


class SetupPasswordUseCase:
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

    def execute(self, cmd: SetupPasswordCommand) -> UserDTO:
        user = self.account_repository.get_by_id(cmd.user_id)
        if not user:
            raise UserNotFoundError("User not found")

        PasswordPolicy.validate(cmd.plain_password)
        password_history = self.account_repository.get_password_history(user.id)
        password_hash = PasswordHash(self.password_hasher.hash(cmd.plain_password))
        user.change_password(
            password_hash,
            plain_password=cmd.plain_password,
            password_history=password_history,
            password_verifier=self.password_hasher.verify,
        )
        saved_user = self.account_repository.save(user)
        for event in user.pull_events():
            self.event_outbox.dispatch(event)
        return to_user_dto(saved_user)


__all__ = ["SetupPasswordUseCase"]
