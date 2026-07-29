"""Django model lookups for identity infrastructure adapters."""

from __future__ import annotations

from typing import Any

from django.apps import apps


def identity_model(model_name: str) -> Any:
    return apps.get_model("identity", model_name)


def user_model() -> Any:
    return identity_model("User")


def oauth_token_model() -> Any:
    return identity_model("OAuthToken")


def identity_session_model() -> Any:
    return identity_model("IdentitySession")


def password_reset_token_model() -> Any:
    return identity_model("PasswordResetToken")


def password_history_entry_model() -> Any:
    return identity_model("PasswordHistoryEntry")


def identity_domain_event_outbox_model() -> Any:
    return identity_model("IdentityDomainEventOutbox")


__all__ = [
    "identity_domain_event_outbox_model",
    "identity_model",
    "identity_session_model",
    "oauth_token_model",
    "password_history_entry_model",
    "password_reset_token_model",
    "user_model",
]
