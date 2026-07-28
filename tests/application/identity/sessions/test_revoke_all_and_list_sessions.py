import uuid
from unittest.mock import Mock

from application.identity.sessions import ListActiveSessionsUseCase, RevokeAllSessionsUseCase
from domain.identity.sessions import IdentitySession, SessionId, SessionStatus, TokenFamily


def _session(family_id: str) -> IdentitySession:
    return IdentitySession(
        id=SessionId(str(uuid.uuid4())),
        user_id=uuid.uuid4(),
        token_family=TokenFamily(family_id),
        status=SessionStatus.ACTIVE,
    )


def test_list_active_sessions_delegates_to_session_repository():
    user_id = uuid.uuid4()
    sessions = (_session("family-one"), _session("family-two"))
    session_repository = Mock()
    session_repository.list_active_identity_sessions.return_value = sessions

    result = ListActiveSessionsUseCase(session_repository=session_repository).execute(user_id=user_id)

    assert result == sessions
    session_repository.list_active_identity_sessions.assert_called_once_with(user_id=user_id)


def test_revoke_all_sessions_blacklists_each_active_family_and_marks_sessions_revoked():
    user_id = uuid.uuid4()
    sessions = (_session("family-one"), _session("family-two"))
    session_repository = Mock()
    session_repository.list_active_identity_sessions.return_value = sessions
    session_repository.revoke_all_identity_sessions.return_value = 2
    token_family_repository = Mock()

    result = RevokeAllSessionsUseCase(
        session_repository=session_repository,
        token_family_repository=token_family_repository,
    ).execute(user_id=user_id, reason="password_changed")

    assert result.revoked_count == 2
    token_family_repository.blacklist_family.assert_any_call("family-one")
    token_family_repository.blacklist_family.assert_any_call("family-two")
    assert token_family_repository.blacklist_family.call_count == 2
    session_repository.revoke_all_identity_sessions.assert_called_once_with(
        user_id=user_id,
        reason="password_changed",
    )
