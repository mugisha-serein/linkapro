"""Change an authenticated account password."""

from application.identity.credentials.change_password_command import ChangePasswordCommand
from application.identity.errors import InvalidCredentialsError, UserNotFoundError
from application.identity.sessions import RevokeAllSessionsUseCase
from application.identity.shared.ports import (
    AccountRepository,
    EventOutbox,
    IdentityUnitOfWork,
    PasswordHasher,
)
from domain.identity.credentials import PasswordHash, PasswordPolicy


class ChangePasswordUseCase:
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
        with self.unit_of_work as unit_of_work:
            user.change_password(
                new_password_hash,
                plain_password=cmd.new_password,
                password_history=password_history,
                password_verifier=self.password_hasher.verify,
            )
            self.account_repository.save(user)
            self.revoke_all_sessions_use_case.execute(
                user_id=user.id,
                reason="password_changed",
            )
            for event in user.pull_events():
                self.event_outbox.dispatch(event)
            unit_of_work.commit()


__all__ = ["ChangePasswordUseCase"]
