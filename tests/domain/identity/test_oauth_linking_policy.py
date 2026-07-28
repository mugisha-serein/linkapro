import uuid
from types import SimpleNamespace

import pytest

from domain.identity.oauth import OAuthLinkingAction, OAuthLinkingPolicy, OAuthProvider


def _account(*, password_hash=None):
    return SimpleNamespace(id=uuid.uuid4(), password_hash=password_hash)


def _link(*, user_id, provider_user_id="google-123"):
    return SimpleNamespace(user_id=user_id, provider_user_id=provider_user_id)


def test_google_email_verification_is_trusted_unless_explicitly_unverified():
    policy = OAuthLinkingPolicy()

    assert policy.is_provider_email_verification_trusted(
        provider=OAuthProvider.GOOGLE,
        provider_email_verified=None,
    )
    assert not policy.is_provider_email_verification_trusted(
        provider=OAuthProvider.GOOGLE,
        provider_email_verified=False,
    )


def test_existing_password_account_can_auto_link_when_provider_email_is_trusted():
    account = _account(password_hash="hash")
    decision = OAuthLinkingPolicy().decide(
        provider=OAuthProvider.GOOGLE,
        provider_user_id="google-123",
        account=account,
        provider_identity_link=None,
        existing_account_link=None,
        provider_email_verified=True,
    )

    assert decision.action is OAuthLinkingAction.LINK_EXISTING_ACCOUNT
    assert decision.can_existing_password_account_auto_link is True
    assert decision.step_up_required is False


def test_provider_identity_owned_by_another_account_is_explicit_decision():
    account = _account()
    decision = OAuthLinkingPolicy().decide(
        provider=OAuthProvider.GOOGLE,
        provider_user_id="google-123",
        account=account,
        provider_identity_link=_link(user_id=uuid.uuid4()),
        existing_account_link=None,
        provider_email_verified=True,
    )

    assert decision.action is OAuthLinkingAction.RELINK_PROVIDER_IDENTITY
    assert decision.provider_identity_owned_by_another_account is True


def test_existing_link_mismatch_is_rejected_by_policy():
    account = _account()

    with pytest.raises(ValueError, match="does not match"):
        OAuthLinkingPolicy().decide(
            provider=OAuthProvider.GOOGLE,
            provider_user_id="google-new",
            account=account,
            provider_identity_link=None,
            existing_account_link=_link(user_id=account.id, provider_user_id="google-old"),
            provider_email_verified=True,
        )
