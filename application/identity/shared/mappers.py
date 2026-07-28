from __future__ import annotations

from application.identity.dtos import AccountDTO, SessionBootstrap
from domain.identity.account import User


def _display_name(*, first_name: str, last_name: str, email: str) -> str:
    return f"{first_name} {last_name}".strip() or first_name or last_name or email


def account_derived_fields(
    *,
    first_name: str,
    last_name: str,
    email: str,
    is_verified: bool,
    has_password: bool,
) -> dict:
    return {
        "display_name": _display_name(first_name=first_name, last_name=last_name, email=email),
        "requires_password_setup": not has_password,
        "onboarding_complete": bool(is_verified and has_password),
    }


def to_account_dto(user: User) -> AccountDTO:
    has_password = bool(user.password_hash)
    derived = account_derived_fields(
        first_name=user.first_name,
        last_name=user.last_name,
        email=str(user.email),
        is_verified=user.is_verified,
        has_password=has_password,
    )
    return AccountDTO(
        id=user.id,
        email=str(user.email),
        first_name=user.first_name,
        last_name=user.last_name,
        role=user.role.value,
        is_active=user.is_active,
        is_verified=user.is_verified,
        created_at=user.created_at,
        last_login=user.last_login,
        display_name=derived["display_name"],
        has_password=has_password,
        requires_password_setup=derived["requires_password_setup"],
        two_factor_enabled=user.two_factor_enabled,
        auth_token_version=user.auth_token_version,
        is_authenticated=True,
        onboarding_complete=derived["onboarding_complete"],
    )


def to_session_bootstrap(user: User) -> SessionBootstrap:
    has_password = bool(user.password_hash)
    derived = account_derived_fields(
        first_name=user.first_name,
        last_name=user.last_name,
        email=str(user.email),
        is_verified=user.is_verified,
        has_password=has_password,
    )
    bootstrap = SessionBootstrap(
        id=user.id,
        email=str(user.email),
        role=user.role.value,
        first_name=user.first_name,
        last_name=user.last_name,
        display_name=derived["display_name"],
        avatar=None,
        is_active=user.is_active,
        is_verified=user.is_verified,
        has_password=has_password,
        requires_password_setup=derived["requires_password_setup"],
        two_factor_enabled=user.two_factor_enabled,
        auth_token_version=getattr(user, "auth_token_version", 0),
        created_at=user.created_at.isoformat() if user.created_at else None,
        last_login=user.last_login.isoformat() if user.last_login else None,
        onboarding_complete=derived["onboarding_complete"],
    )
    return bootstrap


def session_bootstrap_payload(user: User, *, session_id: str | None = None) -> dict:
    values = to_session_bootstrap(user).to_dict()
    if session_id:
        values["session_id"] = str(session_id)
    return values


def session_bootstrap_payload_from_values(
    *,
    id,
    email: str,
    role: str,
    first_name: str,
    last_name: str,
    is_active: bool,
    is_verified: bool,
    has_password: bool,
    two_factor_enabled: bool,
    auth_token_version: int,
    created_at=None,
    last_login=None,
    session_id: str | None = None,
) -> dict:
    derived = account_derived_fields(
        first_name=first_name,
        last_name=last_name,
        email=email,
        is_verified=is_verified,
        has_password=has_password,
    )
    values = {
        "id": str(id),
        "email": email,
        "role": role,
        "first_name": first_name,
        "last_name": last_name,
        "display_name": derived["display_name"],
        "avatar": None,
        "created_at": created_at.isoformat() if created_at else None,
        "last_login": last_login.isoformat() if last_login else None,
        "is_active": is_active,
        "is_verified": is_verified,
        "has_password": has_password,
        "requires_password_setup": derived["requires_password_setup"],
        "two_factor_enabled": two_factor_enabled,
        "auth_token_version": auth_token_version,
        "is_authenticated": True,
        "onboarding_complete": derived["onboarding_complete"],
    }
    if session_id:
        values["session_id"] = str(session_id)
    return values


to_user_dto = to_account_dto
