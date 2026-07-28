"""Unlock a locked identity account."""

from typing import Protocol

from application.identity.commands import UnlockAccountCommand
from application.identity.shared.ports import Clock, IUserRepository
from domain.identity.authorization import RoleAssignmentPolicy

from ._account_administration import (
    load_authorized_account_administration_context,
    save_and_dispatch,
)


class EventOutbox(Protocol):
    def dispatch(self, event) -> None:
        ...


class UnlockAccountUseCase:
    def __init__(
        self,
        *,
        account_repository: IUserRepository,
        event_outbox: EventOutbox,
        clock: Clock,
        role_assignment_policy: RoleAssignmentPolicy | None = None,
    ) -> None:
        self.account_repository = account_repository
        self.event_outbox = event_outbox
        self.clock = clock
        self.role_assignment_policy = role_assignment_policy or RoleAssignmentPolicy()

    def execute(self, cmd: UnlockAccountCommand) -> None:
        context = load_authorized_account_administration_context(
            account_repository=self.account_repository,
            actor_id=cmd.actor_id,
            target_user_id=cmd.target_user_id,
            policy=self.role_assignment_policy,
        )
        context.target.unlock(
            now=self.clock.now(),
            actor_user_id=context.actor.id,
            reason=cmd.reason,
        )
        save_and_dispatch(
            account_repository=self.account_repository,
            event_outbox=self.event_outbox,
            target=context.target,
        )


__all__ = ["UnlockAccountUseCase"]
