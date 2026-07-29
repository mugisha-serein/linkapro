"""Disable MFA for an account."""

from application.identity.mfa.disable_mfa_command import DisableMfaCommand
from application.identity.errors import UserNotFoundError
from application.identity.shared.ports import (
    AccountRepository,
    Clock,
    EventOutbox,
    IdentityUnitOfWork,
    TotpSecretRepository,
)


class DisableMfaUseCase:
    def __init__(
        self,
        *,
        account_repository: AccountRepository,
        totp_secret_repository: TotpSecretRepository,
        event_outbox: EventOutbox,
        clock: Clock,
        unit_of_work: IdentityUnitOfWork,
    ) -> None:
        self.account_repository = account_repository
        self.totp_secret_repository = totp_secret_repository
        self.event_outbox = event_outbox
        self.clock = clock
        self.unit_of_work = unit_of_work

    def execute(self, cmd: DisableMfaCommand) -> None:
        user = self.account_repository.get_by_id(cmd.user_id)
        if not user:
            raise UserNotFoundError("User not found")

        with self.unit_of_work as unit_of_work:
            self.totp_secret_repository.clear_totp_secret(user.id)
            user.disable_two_factor(now=self.clock.now())
            self.account_repository.save(user)
            for event in user.pull_events():
                self.event_outbox.dispatch(event)
            unit_of_work.commit()


__all__ = ["DisableMfaUseCase"]
