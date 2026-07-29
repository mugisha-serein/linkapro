"""Set an initial password for an account."""

from application.identity.credentials.setup_password_command import SetupPasswordCommand
from application.identity.dtos import UserDTO
from application.identity.errors import UserNotFoundError
from application.identity.sessions import RevokeAllSessionsUseCase
from application.identity.shared.mappers import to_user_dto
from application.identity.shared.ports import (
    AccountRepository,
    EventOutbox,
    IdentityUnitOfWork,
    PasswordHasher,
)
from domain.identity.credentials import PasswordHash, PasswordPolicy


class SetupPasswordUseCase:
    def __init__(
        self,
        *,
        account_repository: AccountRepository,
        password_hasher: PasswordHasher,
        event_outbox: EventOutbox,
        revoke_all_sessions_use_case: RevokeAllSessionsUseCase,
        unit_of_work: IdentityUnitOfWork,
    ) -> None:
        self.account_repository = account_repository
        self.password_hasher = password_hasher
        self.event_outbox = event_outbox
        self.revoke_all_sessions_use_case = revoke_all_sessions_use_case
        self.unit_of_work = unit_of_work

    def execute(self, cmd: SetupPasswordCommand) -> UserDTO:
        user = self.account_repository.get_by_id(cmd.user_id)
        if not user:
            raise UserNotFoundError("User not found")

        PasswordPolicy.validate(cmd.plain_password)
        password_history = self.account_repository.get_password_history(user.id)
        password_hash = PasswordHash(self.password_hasher.hash(cmd.plain_password))
        with self.unit_of_work as unit_of_work:
            user.change_password(
                password_hash,
                plain_password=cmd.plain_password,
                password_history=password_history,
                password_verifier=self.password_hasher.verify,
            )
            saved_user = self.account_repository.save(user)
            self.revoke_all_sessions_use_case.execute(
                user_id=user.id,
                reason="password_setup",
            )
            for event in user.pull_events():
                self.event_outbox.dispatch(event)
            unit_of_work.commit()
        return to_user_dto(saved_user)


__all__ = ["SetupPasswordUseCase"]
