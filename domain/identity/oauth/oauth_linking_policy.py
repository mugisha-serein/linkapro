"""OAuth account-linking policy."""

from dataclasses import dataclass
from enum import Enum
from typing import Any

from .oauth_provider import OAuthProvider


class OAuthLinkingAction(str, Enum):
    CREATE_ACCOUNT = "create_account"
    LINK_EXISTING_ACCOUNT = "link_existing_account"
    RELINK_PROVIDER_IDENTITY = "relink_provider_identity"
    UPDATE_EXISTING_LINK = "update_existing_link"


@dataclass(frozen=True)
class OAuthLinkingDecision:
    action: OAuthLinkingAction
    provider_email_verification_trusted: bool
    can_existing_password_account_auto_link: bool
    step_up_required: bool
    provider_identity_owned_by_another_account: bool


class OAuthLinkingPolicy:
    def decide(
        self,
        *,
        provider: OAuthProvider,
        provider_user_id: str,
        account: Any | None,
        provider_identity_link: Any | None,
        existing_account_link: Any | None,
        provider_email_verified: bool | None,
    ) -> OAuthLinkingDecision:
        email_trusted = self.is_provider_email_verification_trusted(
            provider=provider,
            provider_email_verified=provider_email_verified,
        )

        if account is None:
            return OAuthLinkingDecision(
                action=OAuthLinkingAction.CREATE_ACCOUNT,
                provider_email_verification_trusted=email_trusted,
                can_existing_password_account_auto_link=False,
                step_up_required=False,
                provider_identity_owned_by_another_account=False,
            )

        if existing_account_link and existing_account_link.provider_user_id != provider_user_id:
            raise ValueError("Google identity does not match existing linked account")

        owned_by_other_account = bool(
            provider_identity_link and provider_identity_link.user_id != account.id
        )
        can_auto_link = self.can_existing_password_account_auto_link(
            account=account,
            provider_email_verification_trusted=email_trusted,
        )

        if owned_by_other_account:
            action = OAuthLinkingAction.RELINK_PROVIDER_IDENTITY
        elif existing_account_link:
            action = OAuthLinkingAction.UPDATE_EXISTING_LINK
        else:
            action = OAuthLinkingAction.LINK_EXISTING_ACCOUNT

        return OAuthLinkingDecision(
            action=action,
            provider_email_verification_trusted=email_trusted,
            can_existing_password_account_auto_link=can_auto_link,
            step_up_required=False,
            provider_identity_owned_by_another_account=owned_by_other_account,
        )

    @staticmethod
    def is_provider_email_verification_trusted(
        *,
        provider: OAuthProvider,
        provider_email_verified: bool | None,
    ) -> bool:
        if provider is not OAuthProvider.GOOGLE:
            return False
        return provider_email_verified is not False

    @staticmethod
    def can_existing_password_account_auto_link(
        *,
        account: Any,
        provider_email_verification_trusted: bool,
    ) -> bool:
        return bool(account.password_hash) and provider_email_verification_trusted


__all__ = ["OAuthLinkingAction", "OAuthLinkingDecision", "OAuthLinkingPolicy"]
