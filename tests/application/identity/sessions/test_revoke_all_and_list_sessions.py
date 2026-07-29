import uuid
from unittest.mock import Mock

from application.identity.sessions import (
    ActiveSessionDTO,
    ListActiveSessionsUseCase,
    RevokeAllSessionsUseCase,
    RevokeOtherSessionsCommand,
    RevokeOtherSessionsUseCase,
    RevokeSessionCommand,
    RevokeSessionUseCase,
)
from domain.identity.sessions import IdentitySession, SessionId, SessionStatus, TokenFamily


def _session(family_id: str, session_id: uuid.UUID | str | None = None) -> IdentitySession:
    return IdentitySession(
        id=SessionId(str(session_id or uuid.uuid4())),
        user_id=uuid.uuid4(),
        token_family=TokenFamily(family_id),
        status=SessionStatus.ACTIVE,
    )


def test_list_active_sessions_delegates_to_session_repository():
    user_id = uuid.uuid4()
    current_session_id = uuid.uuid4()
    sessions = (_session("family-one", current_session_id), _session("family-two"))
    session_repository = Mock()
    session_repository.list_active_identity_sessions.return_value = sessions

    result = ListActiveSessionsUseCase(session_repository=session_repository).execute(
        user_id=user_id,
        current_session_id=current_session_id,
    )

    assert result == (
        ActiveSessionDTO(
            session_id=str(sessions[0].id),
            token_family="family-one",
            is_current=True,
        ),
        ActiveSessionDTO(
            session_id=str(sessions[1].id),
            token_family="family-two",
            is_current=False,
        ),
    )
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


def test_revoke_named_session_blacklists_family_and_revokes_only_that_session():
    user_id = uuid.uuid4()
    target_session = _session("family-target")
    other_session = _session("family-other")
    session_repository = Mock()
    session_repository.list_active_identity_sessions.return_value = (target_session, other_session)
    token_family_repository = Mock()

    result = RevokeSessionUseCase(
        session_repository=session_repository,
        token_family_repository=token_family_repository,
    ).execute(
        RevokeSessionCommand(
            user_id=user_id,
            session_id=str(target_session.id),
            reason="user_revoked_session",
        )
    )

    assert result.revoked_count == 1
    token_family_repository.blacklist_family.assert_called_once_with("family-target")
    session_repository.revoke_identity_session.assert_called_once_with(
        session_id=str(target_session.id),
        token_family="family-target",
        reason="user_revoked_session",
    )


def test_revoke_named_session_is_idempotent_when_session_is_not_active_for_user():
    user_id = uuid.uuid4()
    session_repository = Mock()
    session_repository.list_active_identity_sessions.return_value = (_session("family-other"),)
    token_family_repository = Mock()

    result = RevokeSessionUseCase(
        session_repository=session_repository,
        token_family_repository=token_family_repository,
    ).execute(
        RevokeSessionCommand(
            user_id=user_id,
            session_id=uuid.uuid4(),
        )
    )

    assert result.revoked_count == 0
    token_family_repository.blacklist_family.assert_not_called()
    session_repository.revoke_identity_session.assert_not_called()


def test_revoke_other_sessions_preserves_current_session():
    user_id = uuid.uuid4()
    current_session = _session("family-current")
    other_session = _session("family-other")
    session_repository = Mock()
    session_repository.list_active_identity_sessions.return_value = (current_session, other_session)
    token_family_repository = Mock()

    result = RevokeOtherSessionsUseCase(
        session_repository=session_repository,
        token_family_repository=token_family_repository,
    ).execute(
        RevokeOtherSessionsCommand(
            user_id=user_id,
            current_session_id=str(current_session.id),
            reason="signed_out_other_devices",
        )
    )

    assert result.revoked_count == 1
    token_family_repository.blacklist_family.assert_called_once_with("family-other")
    session_repository.revoke_identity_session.assert_called_once_with(
        session_id=str(other_session.id),
        token_family="family-other",
        reason="signed_out_other_devices",
    )
