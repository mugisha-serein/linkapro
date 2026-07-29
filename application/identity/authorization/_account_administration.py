"""Shared actor/target authorization helpers for account administration."""

from dataclasses import dataclass

from application.identity.errors import UserNotFoundError
from application.identity.shared.ports import AccountRepository
from domain.identity.account import User
from domain.identity.authorization import (
    RoleAssignmentContext,
    RoleAssignmentPolicy,
    RoleAssignmentRequiresActor,
)


@dataclass(frozen=True)
class AccountAdministrationContext:
    actor: User
    target: User


def load_authorized_account_administration_context(
    *,
    account_repository: AccountRepository,
    actor_id,
    target_user_id,
    policy: RoleAssignmentPolicy | None = None,
) -> AccountAdministrationContext:
    target = account_repository.get_by_id(target_user_id)
    if not target:
        raise UserNotFoundError("User not found")
    if actor_id is None:
        raise RoleAssignmentRequiresActor("Account administration requires an authorizing actor")
    actor = account_repository.get_by_id(actor_id)
    if not actor:
        raise UserNotFoundError("Actor not found")

    (policy or RoleAssignmentPolicy()).ensure_can_assign(
        RoleAssignmentContext.for_actor(
            target_user_id=target.id,
            current_role=target.role,
            new_role=target.role,
            actor_user_id=actor.id,
            actor_role=actor.role,
        )
    )
    return AccountAdministrationContext(actor=actor, target=target)


def save_and_dispatch(*, account_repository: AccountRepository, event_outbox, target: User) -> None:
    account_repository.save(target)
    for event in target.pull_events():
        event_outbox.dispatch(event)
