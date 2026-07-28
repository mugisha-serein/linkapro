from datetime import UTC, datetime

import pytest

from domain.identity.credentials import (
    PasswordHash,
    PasswordHistory,
    PasswordReuseNotAllowed,
    PlainPassword,
)


def _verifier(plain_password: PlainPassword, password_hash: PasswordHash) -> bool:
    return password_hash.reveal_for_password_verification() == f"hash:{plain_password.value}"


def test_password_history_rejects_recently_used_password():
    history = PasswordHistory(
        [
            PasswordHash("hash:FirstValid1!"),
            PasswordHash("hash:SecondValid1!"),
        ],
        max_entries=5,
    )

    with pytest.raises(PasswordReuseNotAllowed):
        history.ensure_not_reused(PlainPassword("SecondValid1!"), _verifier)


def test_password_history_allows_new_password_and_records_latest_first():
    history = PasswordHistory([PasswordHash("hash:OldValid1!")], max_entries=2)
    candidate = PlainPassword("NewValid1!")

    history.ensure_not_reused(candidate, _verifier)
    updated = history.record(
        PasswordHash("hash:NewValid1!"),
        changed_at=datetime(2026, 1, 1, tzinfo=UTC),
    )

    assert [
        entry.password_hash.reveal_for_password_verification()
        for entry in updated.entries
    ] == ["hash:NewValid1!", "hash:OldValid1!"]


def test_password_history_keeps_only_last_n_hashes():
    history = PasswordHistory(
        [
            PasswordHash("hash:1"),
            PasswordHash("hash:2"),
            PasswordHash("hash:3"),
        ],
        max_entries=2,
    )

    assert len(history.entries) == 2
