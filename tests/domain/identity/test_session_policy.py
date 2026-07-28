from domain.identity.sessions import (
    RefreshRejectionReason,
    RefreshTokenReuseDetected,
    RefreshTokenSnapshot,
    RotatedTokenIds,
    SessionRevoked,
    SessionPolicy,
    TokenFamily,
)


def _snapshot() -> RefreshTokenSnapshot:
    return RefreshTokenSnapshot(
        jti="refresh-jti",
        family=TokenFamily("family-id"),
        session_id="session-id",
        user_id="user-id",
        issued_at=123,
        auth_token_version=0,
    )


def test_session_policy_allows_valid_refresh_rotation():
    decision = SessionPolicy().evaluate_refresh_rotation(
        _snapshot(),
        token_already_used=False,
        family_revoked=False,
        user_sessions_revoked=False,
        token_version_matches_active_user=True,
    )

    assert decision.allowed is True
    assert decision.blacklist_presented_token is True
    assert decision.touch_session is True
    assert decision.revoke_family is False


def test_session_policy_detects_refresh_replay_and_revokes_family():
    decision = SessionPolicy().evaluate_refresh_rotation(
        _snapshot(),
        token_already_used=True,
        family_revoked=False,
        user_sessions_revoked=False,
        token_version_matches_active_user=True,
    )

    assert decision.allowed is False
    assert decision.revoke_family is True
    assert decision.revoke_session is True
    assert decision.reason is RefreshRejectionReason.REFRESH_REUSE_DETECTED
    assert decision.error is RefreshTokenReuseDetected


def test_session_policy_rejects_revoked_family():
    decision = SessionPolicy().evaluate_refresh_rotation(
        _snapshot(),
        token_already_used=False,
        family_revoked=True,
        user_sessions_revoked=False,
        token_version_matches_active_user=True,
    )

    assert decision.allowed is False
    assert decision.blacklist_presented_token is True
    assert decision.reason is RefreshRejectionReason.TOKEN_FAMILY_REVOKED


def test_session_policy_rejects_user_session_revocation():
    decision = SessionPolicy().evaluate_refresh_rotation(
        _snapshot(),
        token_already_used=False,
        family_revoked=False,
        user_sessions_revoked=True,
        token_version_matches_active_user=True,
    )

    assert decision.allowed is False
    assert decision.revoke_family is True
    assert decision.reason is RefreshRejectionReason.USER_SESSIONS_REVOKED
    assert decision.error is SessionRevoked


def test_session_policy_rejects_token_version_mismatch():
    decision = SessionPolicy().evaluate_refresh_rotation(
        _snapshot(),
        token_already_used=False,
        family_revoked=False,
        user_sessions_revoked=False,
        token_version_matches_active_user=False,
    )

    assert decision.allowed is False
    assert decision.revoke_family is True
    assert decision.reason is RefreshRejectionReason.SESSION_VERSION_MISMATCH


def test_session_policy_revokes_family_for_sign_out():
    decision = SessionPolicy().revoke_family_for_sign_out(_snapshot())

    assert decision.revoke_family is True
    assert decision.blacklist_presented_token is True
    assert decision.revoke_session is True
    assert decision.reason is RefreshRejectionReason.USER_SIGNED_OUT


def test_token_family_rotate_returns_distinct_token_ids():
    token_ids = TokenFamily("family-id").rotate()
    assert isinstance(token_ids, RotatedTokenIds)
    assert token_ids.access_jti
    assert token_ids.refresh_jti
    assert token_ids.access_jti != token_ids.refresh_jti
