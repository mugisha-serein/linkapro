import uuid
from dataclasses import dataclass, field
from datetime import timedelta
from typing import Optional

from domain.identity.account import User, UserRole
from domain.identity.credentials import Email
from domain.identity.oauth import (
    OAuthAccessToken,
    OAuthLinkingAction,
    OAuthLinkingPolicy,
    OAuthProvider,
    OAuthRefreshToken,
    OAuthToken,
)
from domain.shared.utils import utc_now
from application.identity.auth_policy import AuthenticationStatus, IdentityAuthenticationPolicy
from application.identity.shared.mappers import session_bootstrap_payload
from application.identity.shared.ports import IdentityUnitOfWork, NullIdentityUnitOfWork


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
        unit_of_work: IdentityUnitOfWork | None = None,
    ):
        self.user_repo = user_repo
        self.oauth_repo = oauth_repo
        self.token_service = token_service
        self.session_store = session_store
        self.event_dispatcher = event_dispatcher
        self.unit_of_work = unit_of_work or NullIdentityUnitOfWork()
        self.auth_policy = IdentityAuthenticationPolicy(token_service, session_store)

    def _dispatch_recorded_events(self, user: User) -> None:
        for event in user.pull_events():
            self.event_dispatcher.dispatch(event)

    def execute(
        self,
        user_data: dict,
        token_data: Optional[dict] = None,
        signup_role: Optional[str] = None,
    ) -> GoogleLoginResult:
        with self.unit_of_work as unit_of_work:
            result = self._execute(user_data, token_data=token_data, signup_role=signup_role)
            unit_of_work.commit()
            return result

    def _execute(
        self,
        user_data: dict,
        token_data: Optional[dict] = None,
        signup_role: Optional[str] = None,
    ) -> GoogleLoginResult:
        google_id = (user_data.get("google_id") or "").strip()
        email_raw = (user_data.get("email") or "").strip().lower()
        if not google_id or not email_raw:
            raise ValueError("Google user data missing required fields")

        email = Email(email_raw)
        provider = OAuthProvider.GOOGLE
        access_token_raw = (token_data or {}).get("access_token", "")
        refresh_token_raw = (token_data or {}).get("refresh_token")
        expires_in = int((token_data or {}).get("expires_in") or 3600)

        if not access_token_raw:
            raise ValueError("OAuth token data missing access token")
        access_token = OAuthAccessToken(access_token_raw)
        refresh_token = OAuthRefreshToken(refresh_token_raw) if refresh_token_raw else None

        user = self.user_repo.get_by_email(email)
        oauth_by_google_id = self.oauth_repo.get_by_provider_and_user(provider, google_id)
        existing_user_link = self.oauth_repo.get_by_user_and_provider(user.id, provider) if user else None
        linking_decision = OAuthLinkingPolicy().decide(
            provider=provider,
            provider_user_id=google_id,
            account=user,
            provider_identity_link=oauth_by_google_id,
            existing_account_link=existing_user_link,
            provider_email_verified=self._google_email_verified(user_data),
        )
        linked_now = False
        relinked_now = False
        oauth_token_to_save = None

        if linking_decision.action is OAuthLinkingAction.CREATE_ACCOUNT:
            first_name, last_name = self._split_name(user_data)
            new_user = User.register_new(
                id=uuid.uuid4(),
                email=email,
                password_hash=None,
                first_name=first_name,
                last_name=last_name,
                role=self._resolve_signup_role(signup_role),
                is_verified=True,
            )
            user = self.user_repo.save(new_user)
            self._dispatch_recorded_events(new_user)

            oauth_token = OAuthToken(
                id=uuid.uuid4(),
                user_id=user.id,
                provider=provider,
                provider_user_id=google_id,
                access_token=access_token,
                refresh_token=refresh_token,
                expires_at=utc_now() + timedelta(seconds=expires_in),
            )
            self.oauth_repo.save(oauth_token)
            linked_now = True
        else:
            if linking_decision.action is OAuthLinkingAction.RELINK_PROVIDER_IDENTITY:
                oauth_by_google_id.link_to(user.id, linking_decision, occurred_at=utc_now())
                self._update_oauth_token(
                    oauth_by_google_id,
                    provider_user_id=google_id,
                    access_token=access_token,
                    refresh_token=refresh_token,
                    expires_in=expires_in,
                )
                oauth_token_to_save = oauth_by_google_id
                linked_now = True
                relinked_now = True
            elif linking_decision.action is OAuthLinkingAction.UPDATE_EXISTING_LINK:
                self._update_oauth_token(
                    existing_user_link,
                    provider_user_id=google_id,
                    access_token=access_token,
                    refresh_token=refresh_token,
                    expires_in=expires_in,
                )
                oauth_token_to_save = existing_user_link
            elif linking_decision.action is OAuthLinkingAction.LINK_EXISTING_ACCOUNT:
                oauth_token = oauth_by_google_id or OAuthToken(
                    id=uuid.uuid4(),
                    user_id=user.id,
                    provider=provider,
                    provider_user_id=google_id,
                    access_token=access_token,
                    refresh_token=refresh_token,
                    expires_at=utc_now() + timedelta(seconds=expires_in),
                )
                self._update_oauth_token(
                    oauth_token,
                    provider_user_id=google_id,
                    access_token=access_token,
                    refresh_token=refresh_token,
                    expires_in=expires_in,
                )
                oauth_token_to_save = oauth_token
                linked_now = True

        if linked_now:
            if relinked_now:
                user.relink_oauth_provider(provider)
            else:
                user.link_oauth_provider(provider)
            self.user_repo.save(user)
            self._dispatch_recorded_events(user)

        decision = self.auth_policy.evaluate_oauth_login(user)
        if oauth_token_to_save and decision.status in (
            AuthenticationStatus.AUTHENTICATED,
            AuthenticationStatus.MFA_REQUIRED,
        ):
            self.oauth_repo.save(oauth_token_to_save)

        if decision.status is AuthenticationStatus.MFA_REQUIRED:
            return GoogleLoginResult(requires_2fa=True, temp_token=decision.temp_token)
        if decision.status is not AuthenticationStatus.AUTHENTICATED:
            raise ValueError(f"Authentication failed: {decision.status.value}")

        user.record_login()
        self.user_repo.save(user)
        self._dispatch_recorded_events(user)
        return GoogleLoginResult(
            requires_2fa=False,
            access=decision.access_token,
            refresh=decision.refresh_token,
            bootstrap_user=decision.bootstrap_user or session_bootstrap_payload(user),
        )

    @staticmethod
    def _resolve_signup_role(signup_role: Optional[str]) -> UserRole:
        normalized = (signup_role or "").strip().lower()
        if normalized == UserRole.VENDOR.value:
            return UserRole.VENDOR
        if normalized == UserRole.PLANNER.value:
            return UserRole.PLANNER
        raise ValueError("OAuth signup role is required")

    @staticmethod
    def _split_name(user_data: dict) -> tuple[str, str]:
        first_name = (user_data.get("given_name") or "").strip()
        last_name = (user_data.get("family_name") or "").strip()
        if first_name:
            return first_name, last_name or "User"

        full_name = (user_data.get("name") or "").strip()
        if full_name:
            parts = full_name.split(maxsplit=1)
            if len(parts) == 1:
                return parts[0], "User"
            return parts[0], parts[1]

        return "Google", "User"

    @staticmethod
    def _google_email_verified(user_data: dict) -> bool | None:
        value = user_data.get("email_verified", user_data.get("verified_email"))
        if value is None:
            return None
        return bool(value)

    @staticmethod
    def _update_oauth_token(
        oauth_token: OAuthToken,
        provider_user_id: str,
        access_token: OAuthAccessToken,
        refresh_token: Optional[OAuthRefreshToken],
        expires_in: int,
    ) -> None:
        oauth_token.provider_user_id = provider_user_id
        oauth_token.update_tokens(
            access_token=access_token,
            refresh_token=refresh_token,
            expires_at=utc_now() + timedelta(seconds=expires_in),
        )
