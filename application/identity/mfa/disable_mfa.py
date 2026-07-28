"""Disable MFA for an account."""

from typing import Protocol

from application.identity.commands import DisableMfaCommand
from application.identity.errors import UserNotFoundError
from application.identity.shared.ports import Clock, ITOTPSecretRepository, IUserRepository


class EventOutbox(Protocol):
    def dispatch(self, event) -> None:
        ...


class DisableMfaUseCase:
    def __init__(
        self,
        *,
        account_repository: IUserRepository,
        totp_secret_repository: ITOTPSecretRepository,
        event_outbox: EventOutbox,
        clock: Clock,
    ) -> None:
        self.account_repository = account_repository
        self.totp_secret_repository = totp_secret_repository
        self.event_outbox = event_outbox
        self.clock = clock

    def execute(self, cmd: DisableMfaCommand) -> None:
        user = self.account_repository.get_by_id(cmd.user_id)
        if not user:
            raise UserNotFoundError("User not found")

        self.totp_secret_repository.clear_totp_secret(user.id)
        user.disable_two_factor(now=self.clock.now())
        self.account_repository.save(user)
        for event in user.pull_events():
            self.event_outbox.dispatch(event)


__all__ = ["DisableMfaUseCase"]
