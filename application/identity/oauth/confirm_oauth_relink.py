"""Confirm OAuth identity relinking after step-up verification."""

from __future__ import annotations

from dataclasses import dataclass, field
import uuid

from application.identity.errors import OAuthRelinkRequiresStepUp, UserNotFoundError
from application.identity.shared.ports import (
    AccountRepository,
    Clock,
    EventOutbox,
    IdentityUnitOfWork,
    NullIdentityUnitOfWork,
    OAuthIdentityRepository,
    StepUpGrantVerifier,
)
from domain.identity.oauth import OAuthLinkingAction, OAuthLinkingPolicy, OAuthProvider


OAUTH_RELINK_STEP_UP_PURPOSE = "oauth_relink"


@dataclass(frozen=True)
class ConfirmOAuthRelinkCommand:
    target_user_id: uuid.UUID
    provider: OAuthProvider
    provider_user_id: str
    step_up_grant: str = field(repr=False)
    provider_email_verified: bool | None = None


class ConfirmOAuthRelinkUseCase:
    def __init__(
        self,
        *,
        account_repository: AccountRepository,
        oauth_repository: OAuthIdentityRepository,
        step_up_grant_verifier: StepUpGrantVerifier,
        event_outbox: EventOutbox,
        clock: Clock,
        unit_of_work: IdentityUnitOfWork | None = None,
        oauth_linking_policy: OAuthLinkingPolicy | None = None,
    ) -> None:
        self.account_repository = account_repository
        self.oauth_repository = oauth_repository
        self.step_up_grant_verifier = step_up_grant_verifier
        self.event_outbox = event_outbox
        self.clock = clock
        self.unit_of_work = unit_of_work or NullIdentityUnitOfWork()
        self.oauth_linking_policy = oauth_linking_policy or OAuthLinkingPolicy()

    def execute(self, cmd: ConfirmOAuthRelinkCommand) -> None:
        with self.unit_of_work as unit_of_work:
            self._execute_locked(cmd)
            unit_of_work.commit()

    def _execute_locked(self, cmd: ConfirmOAuthRelinkCommand) -> None:
        target_account = self.account_repository.get_by_id(cmd.target_user_id)
        if not target_account:
            raise UserNotFoundError("User not found")

        oauth_identity = self.oauth_repository.get_by_provider_and_user(
            cmd.provider,
            cmd.provider_user_id,
        )
        if not oauth_identity:
            raise OAuthRelinkRequiresStepUp("OAuth relink requires an existing provider identity")

        existing_account_link = self.oauth_repository.get_by_user_and_provider(
            target_account.id,
            cmd.provider,
        )
        decision = self.oauth_linking_policy.decide(
            provider=cmd.provider,
            provider_user_id=cmd.provider_user_id,
            account=target_account,
            provider_identity_link=oauth_identity,
            existing_account_link=existing_account_link,
            provider_email_verified=cmd.provider_email_verified,
        )
        if (
            decision.action is not OAuthLinkingAction.RELINK_PROVIDER_IDENTITY
            or not decision.provider_identity_owned_by_another_account
        ):
            raise OAuthRelinkRequiresStepUp("OAuth relink requires a cross-account provider identity")
        if not cmd.step_up_grant:
            raise OAuthRelinkRequiresStepUp("OAuth relink requires step-up verification")
        if not self.step_up_grant_verifier.verify(
            cmd.step_up_grant,
            user_id=target_account.id,
            purpose=OAUTH_RELINK_STEP_UP_PURPOSE,
        ):
            raise OAuthRelinkRequiresStepUp("OAuth relink requires step-up verification")

        oauth_identity.link_to(target_account.id, decision, occurred_at=self.clock.now())
        target_account.relink_oauth_provider(cmd.provider, now=self.clock.now())

        self.account_repository.save(target_account)
        self.oauth_repository.save(oauth_identity)
        self.step_up_grant_verifier.consume(
            cmd.step_up_grant,
            user_id=target_account.id,
            purpose=OAUTH_RELINK_STEP_UP_PURPOSE,
        )
        for event in target_account.pull_events():
            self.event_outbox.dispatch(event)


__all__ = [
    "ConfirmOAuthRelinkCommand",
    "ConfirmOAuthRelinkUseCase",
    "OAUTH_RELINK_STEP_UP_PURPOSE",
]
