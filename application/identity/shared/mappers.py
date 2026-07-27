from __future__ import annotations

from application.identity.dtos import UserDTO
from domain.identity.entities import User


def to_user_dto(user: User) -> UserDTO:
    has_password = bool(user.password_hash)
    display_name = f"{user.first_name} {user.last_name}".strip() or str(user.email)
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
        display_name=display_name,
        has_password=has_password,
        requires_password_setup=not has_password,
        two_factor_enabled=user.two_factor_enabled,
        auth_token_version=user.auth_token_version,
        is_authenticated=True,
        onboarding_complete=user.is_verified and has_password,
    )
