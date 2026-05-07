import uuid
from dataclasses import dataclass
from datetime import timedelta
from typing import Optional

from domain.identity.entities import OAuthToken, User, UserRole
from domain.identity.events import UserLoggedIn, UserOAuthLinked, UserRegistered
from domain.identity.value_objects import Email, OAuthProvider
from domain.shared.utils import utc_now


@dataclass(frozen=True)
class GoogleLoginResult:
    requires_2fa: bool
    temp_token: Optional[str] = None
    access: Optional[str] = None
    refresh: Optional[str] = None


class GoogleLoginUseCase:
    def __init__(self, user_repo, oauth_repo, token_service, event_dispatcher):
        self.user_repo = user_repo
        self.oauth_repo = oauth_repo
        self.token_service = token_service
        self.event_dispatcher = event_dispatcher

    def execute(self, user_data: dict, token_data: Optional[dict] = None) -> GoogleLoginResult:
        google_id = (user_data.get("google_id") or "").strip()
        email_raw = (user_data.get("email") or "").strip().lower()
        if not google_id or not email_raw:
            raise ValueError("Google user data missing required fields")

        email = Email(email_raw)
        provider = OAuthProvider.GOOGLE
        access_token = (token_data or {}).get("access_token", "")
        refresh_token = (token_data or {}).get("refresh_token")
        expires_in = int((token_data or {}).get("expires_in") or 3600)

        if not access_token:
            raise ValueError("OAuth token data missing access token")

        user = self.user_repo.get_by_email(email)
        oauth_by_google_id = self.oauth_repo.get_by_provider_and_user(provider, google_id)
        linked_now = False
        created_now = False

        if user:
            existing_user_link = self.oauth_repo.get_by_user_and_provider(user.id, provider)
            if existing_user_link and existing_user_link.provider_user_id != google_id:
                raise ValueError("Google identity does not match existing linked account")

            if oauth_by_google_id and oauth_by_google_id.user_id != user.id:
                oauth_by_google_id.user_id = user.id
                self._update_oauth_token(
                    oauth_by_google_id,
                    provider_user_id=google_id,
                    access_token=access_token,
                    refresh_token=refresh_token,
                    expires_in=expires_in,
                )
                self.oauth_repo.save(oauth_by_google_id)
                linked_now = True
            elif existing_user_link:
                self._update_oauth_token(
                    existing_user_link,
                    provider_user_id=google_id,
                    access_token=access_token,
                    refresh_token=refresh_token,
                    expires_in=expires_in,
                )
                self.oauth_repo.save(existing_user_link)
            else:
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
                self.oauth_repo.save(oauth_token)
                linked_now = True
        else:
            first_name, last_name = self._split_name(user_data)
            user = User(
                id=uuid.uuid4(),
                email=email,
                password_hash=None,
                first_name=first_name,
                last_name=last_name,
                role=UserRole.PLANNER,
                is_verified=True,
            )
            user = self.user_repo.save(user)
            created_now = True

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

        if created_now:
            self.event_dispatcher.dispatch(
                UserRegistered(
                    user_id=user.id,
                    email=user.email,
                    role=user.role,
                    occurred_at=utc_now(),
                )
            )
        if linked_now:
            self.event_dispatcher.dispatch(
                UserOAuthLinked(
                    user_id=user.id,
                    provider=provider.value,
                    occurred_at=utc_now(),
                )
            )

        if user.two_factor_enabled:
            temp_token = self.token_service.create_temp_token(str(user.id))
            return GoogleLoginResult(requires_2fa=True, temp_token=temp_token)

        user.record_login()
        self.user_repo.save(user)

        access = self.token_service.create_access_token(str(user.id), user.role.value)
        refresh = self.token_service.create_refresh_token(str(user.id))
        self.event_dispatcher.dispatch(
            UserLoggedIn(user_id=user.id, occurred_at=utc_now())
        )
        return GoogleLoginResult(requires_2fa=False, access=access, refresh=refresh)

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
    def _update_oauth_token(
        oauth_token: OAuthToken,
        provider_user_id: str,
        access_token: str,
        refresh_token: Optional[str],
        expires_in: int,
    ) -> None:
        oauth_token.provider_user_id = provider_user_id
        oauth_token.access_token = access_token
        oauth_token.refresh_token = refresh_token
        oauth_token.expires_at = utc_now() + timedelta(seconds=expires_in)
