# Domain Service - Business Logic Coordination
from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime, timedelta
from typing import Optional

from apps.accounts.domain.entities.session import Session
from apps.accounts.domain.entities.user import User
from apps.accounts.domain.value_objects.email import Email
from apps.accounts.domain.value_objects.password import Password


@dataclass
class AuthenticationResult:
    """Result of authentication attempt."""
    success: bool
    user: Optional[User] = None
    session: Optional[Session] = None
    failure_reason: Optional[str] = None


@dataclass
class PasswordValidationResult:
    """Result of password validation."""
    is_valid: bool
    errors: list[str] = None

    def __post_init__(self):
        if self.errors is None:
            self.errors = []


class AuthenticationService:
    """
    Domain service for authentication business logic.

    Contains authentication rules and session management logic
    that spans multiple entities.
    """

    @staticmethod
    def authenticate_user(
        user: User,
        provided_password: str,
        ip_address: str,
        user_agent: str
    ) -> AuthenticationResult:
        """
        Business logic for user authentication.

        This contains the core authentication rules without infrastructure concerns.
        """

        # Check if user can login (business rule)
        if not user.can_login():
            if not user.is_active:
                return AuthenticationResult(
                    success=False,
                    failure_reason="ACCOUNT_INACTIVE"
                )
            elif user.locked_until and user.locked_until > datetime.now():
                return AuthenticationResult(
                    success=False,
                    failure_reason="ACCOUNT_LOCKED"
                )

        # Password verification is handled by infrastructure (ports)
        # Here we just apply business rules after verification

        # For domain logic, we assume password verification succeeded
        # and handle the business consequences

        # Update user state for successful login
        updated_user = user.record_successful_login()

        # Create session with business rules
        session = AuthenticationService._create_session_for_user(
            updated_user, ip_address, user_agent
        )

        return AuthenticationResult(
            success=True,
            user=updated_user,
            session=session
        )

    @staticmethod
    def handle_failed_authentication(user: User) -> User:
        """Business logic for handling failed authentication."""
        updated_user = user.record_failed_login()

        # Additional business rules could include:
        # - Sending security alerts
        # - Updating risk scores
        # - Temporary account restrictions

        return updated_user

    @staticmethod
    def _create_session_for_user(user: User, ip_address: str, user_agent: str) -> Session:
        """Business logic for session creation."""
        # Session expires in 24 hours (business rule)
        expires_at = datetime.now() + timedelta(hours=24)

        # Generate session key (infrastructure would provide actual implementation)
        session_key = f"session_{user.id}_{datetime.now().timestamp()}"

        return Session(
            user_id=user.id,
            session_key=session_key,
            ip_address=ip_address,
            user_agent=user_agent,
            expires_at=expires_at,
            risk_score=0  # Initial risk score
        )

    @staticmethod
    def validate_session_for_authentication(session: Session) -> bool:
        """Business rule: Validate if session can be used for authentication."""
        return session.can_be_used_for_authentication()

    @staticmethod
    def should_extend_session(session: Session) -> bool:
        """Business rule: Determine if session should be extended."""
        # Extend session if it's been used in the last hour
        # and expires within 6 hours
        time_since_last_use = datetime.now() - session.last_used_at
        time_until_expiry = session.expires_at - datetime.now()

        return (time_since_last_use < timedelta(hours=1) and
                time_until_expiry < timedelta(hours=6))

    @staticmethod
    def calculate_session_extension(session: Session) -> datetime:
        """Business rule: Calculate new session expiry time."""
        # Extend by 24 hours from now
        return datetime.now() + timedelta(hours=24)


class PasswordPolicyService:
    """
    Domain service for password policy business logic.
    """

    @staticmethod
    def validate_password_strength(password: str) -> PasswordValidationResult:
        """Business rules for password strength validation."""
        errors = []

        if len(password) < 8:
            errors.append("Password must be at least 8 characters long")

        if not any(c.isupper() for c in password):
            errors.append("Password must contain at least one uppercase letter")

        if not any(c.islower() for c in password):
            errors.append("Password must contain at least one lowercase letter")

        if not any(c.isdigit() for c in password):
            errors.append("Password must contain at least one number")

        if not any(c in "!@#$%^&*(),.?\":{}|<>" for c in password):
            errors.append("Password must contain at least one special character")

        # Check for common weak passwords
        weak_passwords = ['password', '123456', 'qwerty', 'admin', 'letmein']
        if password.lower() in weak_passwords:
            errors.append("Password is too common")

        # Check for sequential characters
        if any(password[i:i+3].isalpha() and ord(password[i+1]) - ord(password[i]) == 1
               for i in range(len(password)-2)):
            errors.append("Password contains sequential characters")

        return PasswordValidationResult(
            is_valid=len(errors) == 0,
            errors=errors
        )

    @staticmethod
    def should_force_password_change(user: User) -> bool:
        """Business rule: Determine if password change should be forced."""
        if not user.last_password_change_at:
            return True  # Never changed

        # Force change every 90 days (business rule)
        days_since_change = (datetime.now() - user.last_password_change_at).days
        return days_since_change > 90

    @staticmethod
    def can_reuse_password(user: User, new_password: Password) -> bool:
        """Business rule: Check if password can be reused."""
        # In a real implementation, this would check password history
        # For domain logic, we define the rule that passwords cannot be reused
        # within the last 5 password changes
        return False  # Simplified: never allow reuse