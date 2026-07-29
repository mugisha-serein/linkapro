from dataclasses import dataclass, field
from typing import Optional

from domain.identity.account import User
from domain.identity.oauth import (
    OAuthLinkingAction,
    OAuthLinkingPolicy,
    OAuthToken,
)
from application.identity.authentication import AuthenticationStatus, AuthenticatedSessionIssuer
from application.identity.errors import OAuthRelinkRequiresStepUp
from application.identity.oauth.google_login_command import GoogleLoginCommand
from application.identity.shared.mappers import session_bootstrap_payload
from application.identity.shared.ports import (
    Clock,
    IdGenerator,
    IdentityUnitOfWork,
)


@dataclass(frozen=True)
class GoogleLoginResult:
    requires_2fa: bool
    temp_token: Optional[str] = field(default=None, repr=False)
    access: Optional[str] = field(default=None, repr=False)
    refresh: Optional[str] = field(default=None, repr=False)
    bootstrap_user: Optional[dict] = None


class GoogleLoginUseCase:
    def __init__(
        self,
        user_repo,
        oauth_repo,
        token_service,
        session_store,
        event_dispatcher,
        clock: Clock,
        id_generator: IdGenerator,
        unit_of_work: IdentityUnitOfWork,
        mfa_challenge_repository=None,
        mfa_policy=None,
    ):
        self.user_repo = user_repo
        self.oauth_repo = oauth_repo
        self.token_service = token_service
        self.session_store = session_store
        self.event_dispatcher = event_dispatcher
        self.clock = clock
        self.id_generator = id_generator
        self.unit_of_work = unit_of_work
        self.session_issuer = AuthenticatedSessionIssuer(
            token_service,
            session_store,
            mfa_challenge_repository=mfa_challenge_repository,
            mfa_policy=mfa_policy,
        )

    def _dispatch_recorded_events(self, user: User) -> None:
        for event in user.pull_events():
            self.event_dispatcher.dispatch(event)

    def execute(self, cmd: GoogleLoginCommand) -> GoogleLoginResult:
        with self.unit_of_work as unit_of_work:
            result = self._execute(cmd)
            unit_of_work.commit()
            return result

    def _execute(self, cmd: GoogleLoginCommand) -> GoogleLoginResult:
        identity = cmd.identity
        provider_user_id = identity.provider_user_id.strip()
        if not provider_user_id:
            raise ValueError("Google user data missing required fields")

        user = self.user_repo.get_by_email(identity.email)
        provider_identity_link = self.oauth_repo.get_by_provider_and_user(identity.provider, provider_user_id)
        existing_user_link = self.oauth_repo.get_by_user_and_provider(user.id, identity.provider) if user else None
        linking_decision = OAuthLinkingPolicy().decide(
            provider=identity.provider,
            provider_user_id=provider_user_id,
            account=user,
            provider_identity_link=provider_identity_link,
            existing_account_link=existing_user_link,
            provider_email_verified=identity.email_verified,
        )
        linked_now = False
        oauth_token_to_save = None
        now = self.clock.now()

        if linking_decision.action is OAuthLinkingAction.CREATE_ACCOUNT:
            new_user = User.register_new(
                id=self.id_generator.new_id(),
                email=identity.email,
                password_hash=None,
                first_name=identity.first_name,
                last_name=identity.last_name,
                role=cmd.signup_role,
                is_verified=True,
                now=now,
            )
            user = self.user_repo.save(new_user)
            self._dispatch_recorded_events(new_user)

            oauth_token = OAuthToken(
                id=self.id_generator.new_id(),
                user_id=user.id,
                provider=identity.provider,
                provider_user_id=provider_user_id,
                access_token=cmd.access_token,
                refresh_token=cmd.refresh_token,
                expires_at=cmd.expires_at,
            )
            self.oauth_repo.save(oauth_token)
            linked_now = True
        else:
            if linking_decision.action is OAuthLinkingAction.RELINK_PROVIDER_IDENTITY:
                raise OAuthRelinkRequiresStepUp("OAuth relink requires step-up verification")
            elif linking_decision.action is OAuthLinkingAction.UPDATE_EXISTING_LINK:
                self._update_oauth_token(
                    existing_user_link,
                    access_token=cmd.access_token,
                    refresh_token=cmd.refresh_token,
                    expires_at=cmd.expires_at,
                )
                oauth_token_to_save = existing_user_link
            elif linking_decision.action is OAuthLinkingAction.LINK_EXISTING_ACCOUNT:
                oauth_token = provider_identity_link or OAuthToken(
                    id=self.id_generator.new_id(),
                    user_id=user.id,
                    provider=identity.provider,
                    provider_user_id=provider_user_id,
                    access_token=cmd.access_token,
                    refresh_token=cmd.refresh_token,
                    expires_at=cmd.expires_at,
                )
                self._update_oauth_token(
                    oauth_token,
                    access_token=cmd.access_token,
                    refresh_token=cmd.refresh_token,
                    expires_at=cmd.expires_at,
                )
                oauth_token_to_save = oauth_token
                linked_now = True

        if linked_now:
            user.link_oauth_provider(identity.provider, now=now)
            self.user_repo.save(user)
            self._dispatch_recorded_events(user)

        decision = self.session_issuer.evaluate_oauth_login(user)
        if oauth_token_to_save and decision.status in (
            AuthenticationStatus.AUTHENTICATED,
            AuthenticationStatus.MFA_REQUIRED,
        ):
            self.oauth_repo.save(oauth_token_to_save)

        if decision.status is AuthenticationStatus.MFA_REQUIRED:
            return GoogleLoginResult(requires_2fa=True, temp_token=decision.temp_token)
        if decision.status is not AuthenticationStatus.AUTHENTICATED:
            raise ValueError(f"Authentication failed: {decision.status.value}")

        user.record_login(now=self.clock.now())
        self.user_repo.save(user)
        self._dispatch_recorded_events(user)
        return GoogleLoginResult(
            requires_2fa=False,
            access=decision.access_token,
            refresh=decision.refresh_token,
            bootstrap_user=decision.bootstrap_user or session_bootstrap_payload(user),
        )

    @staticmethod
    def _update_oauth_token(
        oauth_token: OAuthToken,
        access_token,
        refresh_token,
        expires_at,
    ) -> None:
        oauth_token.update_tokens(
            access_token=access_token,
            refresh_token=refresh_token,
            expires_at=expires_at,
        )
