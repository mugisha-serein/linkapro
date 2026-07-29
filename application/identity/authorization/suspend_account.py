"""Suspend an identity account."""

from application.identity.authorization.suspend_account_command import SuspendAccountCommand
from application.identity.sessions import RevokeAllSessionsUseCase
from application.identity.shared.ports import Clock, EventOutbox, AccountRepository
from domain.identity.authorization import RoleAssignmentPolicy

from ._account_administration import (
    load_authorized_account_administration_context,
    save_and_dispatch,
)


class SuspendAccountUseCase:
    def __init__(
        self,
        *,
        account_repository: AccountRepository,
        event_outbox: EventOutbox,
        clock: Clock,
        revoke_all_sessions_use_case: RevokeAllSessionsUseCase,
        role_assignment_policy: RoleAssignmentPolicy | None = None,
    ) -> None:
        self.account_repository = account_repository
        self.event_outbox = event_outbox
        self.clock = clock
        self.revoke_all_sessions_use_case = revoke_all_sessions_use_case
        self.role_assignment_policy = role_assignment_policy or RoleAssignmentPolicy()

    def execute(self, cmd: SuspendAccountCommand) -> None:
        context = load_authorized_account_administration_context(
            account_repository=self.account_repository,
            actor_id=cmd.actor_id,
            target_user_id=cmd.target_user_id,
            policy=self.role_assignment_policy,
        )
        context.target.suspend(
            cmd.reason,
            now=self.clock.now(),
            actor_user_id=context.actor.id,
        )
        save_and_dispatch(
            account_repository=self.account_repository,
            event_outbox=self.event_outbox,
            target=context.target,
        )
        self.revoke_all_sessions_use_case.execute(
            user_id=context.target.id,
            reason="account_suspended",
        )


__all__ = ["SuspendAccountUseCase"]
