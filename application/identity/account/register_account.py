"""Register a new identity account."""

from typing import Protocol

from application.identity.commands import RegisterUserCommand
from application.identity.dtos import UserDTO
from application.identity.errors import DuplicateUserError
from application.identity.shared.mappers import to_user_dto
from application.identity.shared.ports import (
    Clock,
    IdGenerator,
    IdentityUnitOfWork,
    IUserRepository,
    NullIdentityUnitOfWork,
    PasswordHasher,
)
from domain.identity.account import User
from domain.identity.credentials import PasswordHash


class EventOutbox(Protocol):
    def dispatch(self, event) -> None:
        ...


class RegisterAccountUseCase:
    def __init__(
        self,
        *,
        account_repository: IUserRepository,
        password_hasher: PasswordHasher,
        event_outbox: EventOutbox,
        clock: Clock,
        id_generator: IdGenerator,
        unit_of_work: IdentityUnitOfWork | None = None,
    ) -> None:
        self.account_repository = account_repository
        self.password_hasher = password_hasher
        self.event_outbox = event_outbox
        self.clock = clock
        self.id_generator = id_generator
        self.unit_of_work = unit_of_work or NullIdentityUnitOfWork()

    def execute(self, cmd: RegisterUserCommand) -> UserDTO:
        with self.unit_of_work as unit_of_work:
            existing = self.account_repository.get_by_email(cmd.email)
            if existing:
                raise DuplicateUserError("User with this email already exists")

            hashed = self.password_hasher.hash(cmd.plain_password)
            user = User.register_new(
                id=self.id_generator.new_id(),
                email=cmd.email,
                password_hash=PasswordHash(hashed),
                first_name=cmd.first_name,
                last_name=cmd.last_name,
                role=cmd.role,
                now=self.clock.now(),
            )

            saved_user = self.account_repository.save(user)
            for event in user.pull_events():
                self.event_outbox.dispatch(event)
            result = to_user_dto(saved_user)
            unit_of_work.commit()
            return result


__all__ = ["RegisterAccountUseCase"]
