"""Assign a role to an identity account."""

from typing import Protocol

from application.identity.commands import AssignRoleCommand
from application.identity.shared.ports import Clock, IUserRepository
from domain.identity.account import UserRole
from domain.identity.authorization import RoleAssignmentPolicy

from ._account_administration import (
    load_authorized_account_administration_context,
    save_and_dispatch,
)


class EventOutbox(Protocol):
    def dispatch(self, event) -> None:
        ...


class AssignRoleUseCase:
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

    def execute(self, cmd: AssignRoleCommand) -> None:
        context = load_authorized_account_administration_context(
            account_repository=self.account_repository,
            actor_id=cmd.actor_id,
            target_user_id=cmd.target_user_id,
            policy=self.role_assignment_policy,
        )
        context.target.change_role(
            UserRole(cmd.new_role),
            actor_user_id=context.actor.id,
            actor_role=context.actor.role,
            reason=cmd.reason,
            now=self.clock.now(),
        )
        save_and_dispatch(
            account_repository=self.account_repository,
            event_outbox=self.event_outbox,
            target=context.target,
        )


__all__ = ["AssignRoleUseCase"]
