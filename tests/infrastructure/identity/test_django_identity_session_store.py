import pytest

from interface.identity.models import IdentitySession, User
from infrastructure.identity.django_identity_session_store import DjangoIdentitySessionStore


@pytest.mark.django_db
def test_list_active_identity_sessions_returns_only_active_sessions_ordered_by_last_seen():
    user = User.objects.create_user(
        email="sessions@example.com",
        password="StrongPass1!",
        first_name="Session",
        last_name="User",
        role="planner",
    )
    older = IdentitySession.objects.create(user=user, token_family="family-older")
    newer = IdentitySession.objects.create(user=user, token_family="family-newer")
    IdentitySession.objects.create(
        user=user,
        token_family="family-revoked",
        revoked_at=newer.last_seen_at,
        revoked_reason="signed_out",
    )

    result = DjangoIdentitySessionStore().list_active_identity_sessions(user_id=user.id)

    assert [session.token_family.id for session in result] == [
        "family-newer",
        "family-older",
    ]
    assert all(session.is_active for session in result)


@pytest.mark.django_db
def test_revoke_all_identity_sessions_marks_only_active_sessions_for_user():
    user = User.objects.create_user(
        email="revoke-sessions@example.com",
        password="StrongPass1!",
        first_name="Revoke",
        last_name="Sessions",
        role="planner",
    )
    other_user = User.objects.create_user(
        email="other-sessions@example.com",
        password="StrongPass1!",
        first_name="Other",
        last_name="Sessions",
        role="planner",
    )
    first = IdentitySession.objects.create(user=user, token_family="family-one")
    second = IdentitySession.objects.create(user=user, token_family="family-two")
    other = IdentitySession.objects.create(user=other_user, token_family="family-other")

    count = DjangoIdentitySessionStore().revoke_all_identity_sessions(
        user_id=user.id,
        reason="account_suspended",
    )

    first.refresh_from_db()
    second.refresh_from_db()
    other.refresh_from_db()
    assert count == 2
    assert first.revoked_reason == "account_suspended"
    assert second.revoked_reason == "account_suspended"
    assert first.revoked_at is not None
    assert second.revoked_at is not None
    assert other.revoked_at is None
