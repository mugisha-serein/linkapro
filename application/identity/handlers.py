"""Command and query handlers for identity."""
import uuid
from datetime import datetime, timedelta
from typing import Optional, Tuple

from domain.identity.entities import User, UserRole, OAuthToken
from domain.identity.value_objects import (
    Email,
    PasswordHash,
    PlainPassword,
    OAuthProvider,
)
from domain.shared.utils import utc_now
from domain.identity.interfaces import IUserRepository, IOAuthTokenRepository
from domain.identity.events import (
    UserRegistered,
    UserLoggedIn,
    UserPasswordChanged,
    UserOAuthLinked,
    UserDeactivated,
)
from .commands import (
    RegisterUserCommand,
    LoginUserCommand,
    OAuthLoginCommand,
    ChangePasswordCommand,
    RequestPasswordResetCommand,
    ResetPasswordCommand,
    VerifyEmailCommand,
    UpdateProfileCommand,
    DeactivateUserCommand,
)
from .dtos import UserDTO, AuthenticationResultDTO
from .queries import GetUserByIdQuery, GetUserByEmailQuery




class IdentityCommandHandlers:
    """Orchestrates identity write operations."""

    def __init__(
        self,
        user_repo: IUserRepository,
        oauth_repo: IOAuthTokenRepository,
        password_hasher,  # Infrastructure adapter injected
        token_service,    # Infrastructure adapter for JWT
        event_dispatcher, # Infrastructure event bus
    ):
        self.user_repo = user_repo
        self.oauth_repo = oauth_repo
        self.password_hasher = password_hasher
        self.token_service = token_service
        self.event_dispatcher = event_dispatcher

    def register_user(self, cmd: RegisterUserCommand) -> UserDTO:
        # Check if email already exists
        existing = self.user_repo.get_by_email(cmd.email)
        if existing:
            raise ValueError("User with this email already exists")

        # Hash password
        hashed = self.password_hasher.hash(cmd.plain_password)

        # Create user entity
        user = User(
            id=uuid.uuid4(),
            email=cmd.email,
            password_hash=PasswordHash(hashed),
            first_name=cmd.first_name,
            last_name=cmd.last_name,
            role=UserRole(cmd.role),
        )

        # Persist
        saved_user = self.user_repo.save(user)

        # Dispatch event
        self.event_dispatcher.dispatch(
            UserRegistered(
                user_id=saved_user.id,
                email=saved_user.email,
                role=saved_user.role,
                occurred_at=utc_now(),
            )
        )

        return self._to_dto(saved_user)

    def login_user(self, cmd: LoginUserCommand) -> AuthenticationResultDTO:
        # Fetch user
        user = self.user_repo.get_by_email(cmd.email)
        if not user:
            raise ValueError("Invalid credentials")

        if not user.is_active:
            raise ValueError("Account is deactivated")

        if not user.password_hash:
            raise ValueError("Account uses social login only")

        # Verify password
        if not self.password_hasher.verify(cmd.plain_password, user.password_hash):
            raise ValueError("Invalid credentials")

        # Record login
        user.record_login()
        self.user_repo.save(user)

        # Generate tokens
        access_token = self.token_service.create_access_token(str(user.id), user.role.value)
        refresh_token = self.token_service.create_refresh_token(str(user.id))

        # Dispatch event
        self.event_dispatcher.dispatch(UserLoggedIn(user_id=user.id, occurred_at=utc_now()))

        return AuthenticationResultDTO(
            user=self._to_dto(user),
            access_token=access_token,
            refresh_token=refresh_token,
        )

    def oauth_login(self, cmd: OAuthLoginCommand) -> AuthenticationResultDTO:
        # Try to find existing OAuth link
        oauth_token = self.oauth_repo.get_by_provider_and_user(
            cmd.provider, cmd.provider_user_id
        )
        if oauth_token:
            # Existing OAuth user: retrieve user and update token
            user = self.user_repo.get_by_id(oauth_token.user_id)
            if not user:
                raise ValueError("User not found")
            # Update token (new access token)
            oauth_token.access_token = cmd.access_token
            oauth_token.refresh_token = cmd.refresh_token
            oauth_token.expires_at = utc_now() + timedelta(seconds=cmd.expires_in)
            self.oauth_repo.save(oauth_token)
        else:
            # New OAuth user: check if email exists
            user = self.user_repo.get_by_email(cmd.email)
            if user:
                # Existing email: link OAuth to existing user (if allowed)
                # For simplicity, we'll raise error if user exists but no OAuth link
                # In real scenario, you might want to link automatically or prompt user.
                raise ValueError("Email already registered. Please log in with password or link account.")
            else:
                # Create new user
                user = User(
                    id=uuid.uuid4(),
                    email=cmd.email,
                    password_hash=None,  # No password for OAuth users
                    first_name=cmd.first_name,
                    last_name=cmd.last_name,
                    role=UserRole.PLANNER,  # Default role; can be changed later
                    is_verified=True,       # OAuth email is verified
                )
                user = self.user_repo.save(user)

                # Create OAuth token
                oauth_token = OAuthToken(
                    id=uuid.uuid4(),
                    user_id=user.id,
                    provider=cmd.provider,
                    provider_user_id=cmd.provider_user_id,
                    access_token=cmd.access_token,
                    refresh_token=cmd.refresh_token,
                    expires_at=utc_now() + timedelta(seconds=cmd.expires_in),
                )
                self.oauth_repo.save(oauth_token)

                self.event_dispatcher.dispatch(
                    UserOAuthLinked(
                        user_id=user.id,
                        provider=cmd.provider.value,
                        occurred_at=utc_now(),
                    )
                )
                self.event_dispatcher.dispatch(
                    UserRegistered(
                        user_id=user.id,
                        email=user.email,
                        role=user.role,
                        occurred_at=utc_now(),
                    )
                )

        # Record login
        user.record_login()
        self.user_repo.save(user)

        # Generate tokens
        access_token = self.token_service.create_access_token(str(user.id), user.role.value)
        refresh_token = self.token_service.create_refresh_token(str(user.id))

        self.event_dispatcher.dispatch(UserLoggedIn(user_id=user.id, occurred_at=utc_now()))

        return AuthenticationResultDTO(
            user=self._to_dto(user),
            access_token=access_token,
            refresh_token=refresh_token,
        )

    def change_password(self, cmd: ChangePasswordCommand) -> None:
        user = self.user_repo.get_by_id(cmd.user_id)
        if not user:
            raise ValueError("User not found")
        if not user.password_hash:
            raise ValueError("Account does not use password authentication")

        # Verify old password
        if not self.password_hasher.verify(cmd.old_plain_password, user.password_hash):
            raise ValueError("Current password is incorrect")

        # Hash new password
        new_hash = self.password_hasher.hash(cmd.new_plain_password)
        user.change_password(PasswordHash(new_hash))
        self.user_repo.save(user)

        self.event_dispatcher.dispatch(
            UserPasswordChanged(user_id=user.id, occurred_at=utc_now())
        )

    def request_password_reset(self, cmd: RequestPasswordResetCommand) -> None:
        user = self.user_repo.get_by_email(cmd.email)
        if not user:
            # Don't reveal existence; just return silently
            return

        # Create reset token (short-lived, one-time use)
        reset_token = self.token_service.create_password_reset_token(str(user.id))
        # In real implementation, we would store token hash or use a separate table.
        # For now, we'll dispatch an event that triggers an email.
        self.event_dispatcher.dispatch(
            # PasswordResetRequested event (to be defined) will be handled by application event handler to send email
            # We'll define a simple event for this purpose.
            object()  # Placeholder: define PasswordResetRequested event
        )

    def reset_password(self, cmd: ResetPasswordCommand) -> None:
        # Validate reset token
        user_id_str = self.token_service.verify_password_reset_token(cmd.reset_token)
        if not user_id_str:
            raise ValueError("Invalid or expired reset token")

        user_id = uuid.UUID(user_id_str)
        user = self.user_repo.get_by_id(user_id)
        if not user:
            raise ValueError("User not found")

        # Hash new password
        new_hash = self.password_hasher.hash(cmd.new_plain_password)
        user.change_password(PasswordHash(new_hash))
        self.user_repo.save(user)

        # Optionally invalidate token (if stored) - not implemented here

        self.event_dispatcher.dispatch(
            UserPasswordChanged(user_id=user.id, occurred_at=utc_now())
        )

    def verify_email(self, cmd: VerifyEmailCommand) -> None:
        user_id_str = self.token_service.verify_email_verification_token(cmd.verification_token)
        if not user_id_str:
            raise ValueError("Invalid or expired verification token")

        user_id = uuid.UUID(user_id_str)
        user = self.user_repo.get_by_id(user_id)
        if not user:
            raise ValueError("User not found")

        user.mark_verified()
        self.user_repo.save(user)

    def update_profile(self, cmd: UpdateProfileCommand) -> UserDTO:
        user = self.user_repo.get_by_id(cmd.user_id)
        if not user:
            raise ValueError("User not found")

        if cmd.first_name is not None:
            user.first_name = cmd.first_name
        if cmd.last_name is not None:
            user.last_name = cmd.last_name

        saved = self.user_repo.save(user)
        return self._to_dto(saved)

    def deactivate_user(self, cmd: DeactivateUserCommand) -> None:
        user = self.user_repo.get_by_id(cmd.user_id)
        if not user:
            raise ValueError("User not found")

        user.deactivate()
        self.user_repo.save(user)

        self.event_dispatcher.dispatch(
            UserDeactivated(user_id=user.id, occurred_at=utc_now())
        )

    def _to_dto(self, user: User) -> UserDTO:
        return UserDTO(
            id=user.id,
            email=str(user.email),
            first_name=user.first_name,
            last_name=user.last_name,
            role=user.role.value,
            is_active=user.is_active,
            is_verified=user.is_verified,
            created_at=user.created_at,
            last_login=user.last_login,
        )


class IdentityQueryHandlers:
    """Read-only queries for identity."""

    def __init__(self, user_repo: IUserRepository):
        self.user_repo = user_repo

    def get_user_by_id(self, query: GetUserByIdQuery) -> Optional[UserDTO]:
        user = self.user_repo.get_by_id(query.user_id)
        if not user:
            return None
        return UserDTO(
            id=user.id,
            email=str(user.email),
            first_name=user.first_name,
            last_name=user.last_name,
            role=user.role.value,
            is_active=user.is_active,
            is_verified=user.is_verified,
            created_at=user.created_at,
            last_login=user.last_login,
        )

    def get_user_by_email(self, query: GetUserByEmailQuery) -> Optional[UserDTO]:
        user = self.user_repo.get_by_email(query.email)
        if not user:
            return None
        return UserDTO(
            id=user.id,
            email=str(user.email),
            first_name=user.first_name,
            last_name=user.last_name,
            role=user.role.value,
            is_active=user.is_active,
            is_verified=user.is_verified,
            created_at=user.created_at,
            last_login=user.last_login,
        )