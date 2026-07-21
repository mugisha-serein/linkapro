from django.core.cache import cache

import pyotp
import base64
import qrcode
from io import BytesIO
import uuid
from datetime import datetime, timedelta
from typing import Optional, Tuple

from domain.identity.entities import User, UserRole, OAuthToken
from domain.identity.value_objects import (
    Email,
    PasswordHash,
    PlainPassword,
    OAuthProvider,
    TOTPSecret,
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
from .auth_policy import AuthenticationDecision, AuthenticationStatus, IdentityAuthenticationPolicy
from .commands import (
    EnableTwoFactorCommand,
    LoginTwoFactorCommand,
    RegisterUserCommand,
    LoginUserCommand,
    OAuthLoginCommand,
    ChangePasswordCommand,
    RequestPasswordResetCommand,
    ResetPasswordCommand,
    VerifyEmailCommand,
    UpdateProfileCommand,
    DeactivateUserCommand,
    VerifyTwoFactorSetupCommand,
)
from .dtos import TwoFactorSetupDTO, UserDTO
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
        self.auth_policy = IdentityAuthenticationPolicy(token_service)

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

    def login_user(self, cmd: LoginUserCommand) -> AuthenticationDecision:
        user = self.user_repo.get_by_email(cmd.email)
        decision = self.auth_policy.evaluate_password_login(
            user=user,
            plain_password=cmd.plain_password,
            password_hasher=self.password_hasher,
        )

        if decision.status is not AuthenticationStatus.AUTHENTICATED:
            return decision

        if user:
            user.record_login()
            self.user_repo.save(user)
            self.event_dispatcher.dispatch(
                UserLoggedIn(user_id=user.id, occurred_at=utc_now())
            )

        return decision

    def oauth_login(self, cmd: OAuthLoginCommand) -> AuthenticationDecision:
        # Try to find existing OAuth link
        oauth_token = self.oauth_repo.get_by_provider_and_user(
            cmd.provider, cmd.provider_user_id
        )
        if oauth_token:
            # Existing OAuth user: retrieve user and update token
            user = self.user_repo.get_by_id(oauth_token.user_id)
            if not user:
                raise ValueError("User not found")
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

        decision = self.auth_policy.evaluate_oauth_login(user)
        if oauth_token and decision.status in (
            AuthenticationStatus.AUTHENTICATED,
            AuthenticationStatus.MFA_REQUIRED,
        ):
            oauth_token.update_tokens(
                access_token=cmd.access_token,
                refresh_token=cmd.refresh_token,
                expires_at=utc_now() + timedelta(seconds=cmd.expires_in),
            )
            self.oauth_repo.save(oauth_token)

        if decision.status is not AuthenticationStatus.AUTHENTICATED:
            return decision

        user.record_login()
        self.user_repo.save(user)

        self.event_dispatcher.dispatch(
            UserLoggedIn(user_id=user.id, occurred_at=utc_now())
        )

        return decision

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
    
    def enable_two_factor(self, cmd: EnableTwoFactorCommand) -> TwoFactorSetupDTO:
        user = self.user_repo.get_by_id(cmd.user_id)
        if not user:
            raise ValueError("User not found")

        # Generate new TOTP secret
        secret = pyotp.random_base32()
        provisioning_uri = pyotp.totp.TOTP(secret).provisioning_uri(
            name=user.email.value,
            issuer_name="Linkapro"
        )

        # Generate QR code as base64 (optional, can be done client-side)
        img = qrcode.make(provisioning_uri)
        buffer = BytesIO()
        img.save(buffer, format="PNG")
        qr_base64 = base64.b64encode(buffer.getvalue()).decode()

        # Store secret temporarily (pending verification)
        # We'll use Django's cache or a separate field
        cache.set(f"totp_setup_{user.id}", secret, timeout=600)  # 10 minutes

        return TwoFactorSetupDTO(
            secret=secret,
            provisioning_uri=provisioning_uri,
            qr_code_base64=qr_base64,
        )

    def verify_two_factor_setup(self, cmd: VerifyTwoFactorSetupCommand) -> None:
        user = self.user_repo.get_by_id(cmd.user_id)
        if not user:
            raise ValueError("User not found")

        secret = cache.get(f"totp_setup_{user.id}")
        if not secret:
            raise ValueError("TOTP setup expired or not initiated")

        totp = pyotp.TOTP(secret)
        if not totp.verify(cmd.token):
            raise ValueError("Invalid TOTP token")

        # Store the secret permanently and enable 2FA
        self.user_repo.set_totp_secret(user.id, TOTPSecret(secret))
        cache.delete(f"totp_setup_{user.id}")

    def login_two_factor(self, cmd: LoginTwoFactorCommand) -> AuthenticationDecision:
        # Decode temp token to get user_id and check it's not expired
        payload = self.token_service.verify_temp_token(cmd.temp_token)
        if not payload:
            return AuthenticationDecision(
                status=AuthenticationStatus.INVALID_TEMP_TOKEN
            )

        user_id = uuid.UUID(payload["user_id"])
        user = self.user_repo.get_by_id(user_id)
        if not user or not user.is_active:
            return AuthenticationDecision(
                status=AuthenticationStatus.INACTIVE if user and not user.is_active else AuthenticationStatus.INVALID_TEMP_TOKEN
            )

        # Verify TOTP
        secret = self.user_repo.get_totp_secret(user.id)
        if not secret:
            return AuthenticationDecision(
                status=AuthenticationStatus.INVALID_TEMP_TOKEN
            )

        totp = pyotp.TOTP(secret.reveal_for_totp_verification())
        if not totp.verify(cmd.token):
            return AuthenticationDecision(
                status=AuthenticationStatus.INVALID_MFA_CODE
            )

        user.record_login()
        self.user_repo.save(user)

        self.event_dispatcher.dispatch(
            UserLoggedIn(user_id=user.id, occurred_at=utc_now())
        )

        return self.auth_policy.issue_authenticated_login(user)

    def _to_dto(self, user: User) -> UserDTO:
        has_password = bool(user.password_hash)
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
            display_name=f"{user.first_name} {user.last_name}".strip() or str(user.email),
            has_password=has_password,
            requires_password_setup=not has_password,
            two_factor_enabled=user.two_factor_enabled,
            is_authenticated=True,
            onboarding_complete=user.is_verified and has_password,
        )


class IdentityQueryHandlers:
    """Read-only queries for identity."""

    def __init__(self, user_repo: IUserRepository):
        self.user_repo = user_repo

    def get_user_by_id(self, query: GetUserByIdQuery) -> Optional[UserDTO]:
        user = self.user_repo.get_by_id(query.user_id)
        if not user:
            return None
        has_password = bool(user.password_hash)
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
            display_name=f"{user.first_name} {user.last_name}".strip() or str(user.email),
            has_password=has_password,
            requires_password_setup=not has_password,
            two_factor_enabled=user.two_factor_enabled,
            is_authenticated=True,
            onboarding_complete=user.is_verified and has_password,
        )

    def get_user_by_email(self, query: GetUserByEmailQuery) -> Optional[UserDTO]:
        user = self.user_repo.get_by_email(query.email)
        if not user:
            return None
        has_password = bool(user.password_hash)
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
            display_name=f"{user.first_name} {user.last_name}".strip() or str(user.email),
            has_password=has_password,
            requires_password_setup=not has_password,
            two_factor_enabled=user.two_factor_enabled,
            is_authenticated=True,
            onboarding_complete=user.is_verified and has_password,
        )
