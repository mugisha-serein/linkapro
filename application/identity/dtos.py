"""Data Transfer Objects for identity module."""
from dataclasses import dataclass
from datetime import datetime
from typing import Optional
import uuid


@dataclass(frozen=True)
class UserDTO:
    id: uuid.UUID
    email: str
    first_name: str
    last_name: str
    role: str
    is_active: bool
    is_verified: bool
    created_at: datetime
    last_login: Optional[datetime]


@dataclass(frozen=True)
class AuthenticationResultDTO:
    user: UserDTO
    access_token: str
    refresh_token: str
    token_type: str = "Bearer"