import time
from unittest.mock import Mock

from application.identity.sessions import RefreshSessionUseCase, RevokeCurrentSessionUseCase
from application.identity.shared.dtos import IssuedTokenPair, RefreshTokenClaims, TokenBootstrapClaims


def _claims() -> RefreshTokenClaims:
    return RefreshTokenClaims(
        raw="raw-refresh-token",
        jti="presented-jti",
        family="family-id",
        user_id="user-id",
        session_id="session-id",
        issued_at=100,
        expires_at=int(time.time()) + 3600,
        auth_token_version=2,
    )


def _session_store():
    store = Mock()
    store.is_token_revoked_for_user.return_value = False
    store.token_version_matches_active_user.return_value = True
    store.get_bootstrap_claims.return_value = {"id": "user-id", "session_id": "session-id"}
    return store


def test_refresh_session_rotates_token_family_with_typed_claims():
    claims = _claims()
    blacklist = Mock()
    blacklist.is_blacklisted.return_value = False
    blacklist.is_family_blacklisted.return_value = False
    session_store = _session_store()
    token_service = Mock()
    token_service.inspect_refresh_token.return_value = claims
    token_service.issue_rotated_pair.return_value = IssuedTokenPair(
        access_token="new-access",
        refresh_token="new-refresh",
        bootstrap_claims=TokenBootstrapClaims({"id": "user-id"}),
    )

    access_token, refresh_token, bootstrap = RefreshSessionUseCase(
        blacklist=blacklist,
        session_repository=session_store,
        session_security_state_reader=session_store,
        session_bootstrap_reader=session_store,
        token_service=token_service,
    ).execute("raw-refresh-token")

    assert access_token == "new-access"
    assert refresh_token == "new-refresh"
    assert bootstrap == {"id": "user-id"}
    request = token_service.issue_rotated_pair.call_args.args[0]
    assert request.claims is claims
    assert request.access_jti
    assert request.refresh_jti
    assert request.access_jti != request.refresh_jti
    blacklist.blacklist.assert_called_once()
    blacklist.blacklist_family.assert_not_called()
    session_store.touch_identity_session.assert_called_once_with("session-id", "family-id")


def test_revoke_session_revokes_presented_token_family():
    claims = _claims()
    blacklist = Mock()
    session_store = Mock()
    token_service = Mock()
    token_service.inspect_refresh_token.return_value = claims

    RevokeCurrentSessionUseCase(
        blacklist=blacklist,
        session_repository=session_store,
        token_service=token_service,
    ).execute("raw-refresh-token")

    token_service.inspect_refresh_token.assert_called_once_with(
        "raw-refresh-token",
        context="refresh_token_revoke",
    )
    blacklist.blacklist.assert_called_once()
    blacklist.blacklist_family.assert_called_once_with("family-id")
    session_store.revoke_identity_session.assert_called_once_with(
        session_id="session-id",
        token_family="family-id",
        reason="user_signed_out",
    )
