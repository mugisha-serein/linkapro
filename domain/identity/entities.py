"""Identity domain entities."""
import uuid
from dataclasses import dataclass, field
from datetime import datetime
from enum import Enum
from typing import Optional, List

from domain.shared.utils import utc_now
from .value_objects import ApprovedPasswordChange, Email, PasswordHash, OAuthProvider


class UserRole(str, Enum):
    PLANNER = "planner"
    VENDOR = "vendor"
    ADMIN = "admin"


@dataclass
class User:
    id: uuid.UUID
    email: Email
    password_hash: Optional[PasswordHash]
    first_name: str
    last_name: str
    role: UserRole
    two_factor_enabled: bool = False
    auth_token_version: int = 0
    is_active: bool = True
    is_verified: bool = False
    created_at: datetime = field(default_factory=utc_now)
    updated_at: datetime = field(default_factory=utc_now)
    last_login: Optional[datetime] = None
    domain_events: List[object] = field(default_factory=list, init=False, repr=False)

    def change_password(
        self, password_change: PasswordHash | ApprovedPasswordChange
    ) -> None:
        """Update password hash and record change."""
        new_password_hash = (
            password_change.new_password_hash
            if isinstance(password_change, ApprovedPasswordChange)
            else password_change
        )
        changed_at = utc_now()
        self.password_hash = new_password_hash
        self.auth_token_version += 1
        self.updated_at = changed_at
        self._record_password_changed(changed_at)

    def _record_password_changed(self, occurred_at: datetime) -> None:
        from .events import UserPasswordChanged

        self.domain_events.append(
            UserPasswordChanged(user_id=self.id, occurred_at=occurred_at)
        )

    def mark_verified(self) -> None:
        self.is_verified = True
        self.updated_at = utc_now()

    def deactivate(self) -> None:
        self.is_active = False
        self.updated_at = utc_now()

    def activate(self) -> None:
        self.is_active = True
        self.updated_at = utc_now()

    def record_login(self) -> None:
        self.last_login = utc_now()


@dataclass
class OAuthToken:
    id: uuid.UUID
    user_id: uuid.UUID
    provider: OAuthProvider
    provider_user_id: str
    access_token: str
    refresh_token: Optional[str]
    expires_at: datetime
    created_at: datetime = field(default_factory=utc_now)

    def is_expired(self) -> bool:
        return utc_now() >= self.expires_at
