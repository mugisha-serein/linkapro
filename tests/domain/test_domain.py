# tests/test_domain.py
# Pure Python tests — no Django, no database, no HTTP
# Run with: python -m pytest tests/ -v

import sys
import os
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

import pytest
from datetime import timedelta

from domain import (
    # Value Objects
    HashedPassword, DeviceFingerprintValue,
    UserId, SessionId, TokenId, TokenFamilyId,
    RoleType, SessionStatus, LoginOutcome, TokenStatus,
    utc_now,
    # Entities
    User, Role, UserRole, Session, DeviceFingerprint,
    RefreshToken, LoginActivity,
    MAX_FAILED_ATTEMPTS, LOCK_DURATION_MINUTES,
    # Services
    AuthenticationService, SessionService, TokenService,
    # Exceptions
    AccountInactiveError, AccountLockedError,
    SessionExpiredError, SessionRevokedError, SessionOwnershipError,
    DeviceBindingError,
    TokenReuseDetectedError, TokenExpiredError, TokenFamilyCompromisedError,
    RoleAlreadyAssignedError, RoleNotFoundError, UnauthorizedError,
    InvalidEmailError, InvalidPasswordError, InvalidFingerprintError,
)


# ══════════════════════════════════════════════════════════
# FIXTURES
# ══════════════════════════════════════════════════════════

VALID_HASH = "a" * 64   # satisfies the 60-char minimum

def make_email(addr="user@example.com") -> Email:
    return Email(address=addr)

def make_password() -> HashedPassword:
    return HashedPassword(value=VALID_HASH)

def make_user(email="user@example.com") -> User:
    return User.create(email=make_email(email), hashed_password=make_password())

def make_session(user: User) -> Session:
    return Session.create(user_id=user.id, ip_address="1.2.3.4", user_agent="TestAgent/1.0")

def make_fingerprint_value() -> DeviceFingerprintValue:
    return DeviceFingerprintValue(raw="a" * 64)


# ══════════════════════════════════════════════════════════
# VALUE OBJECT TESTS
# ══════════════════════════════════════════════════════════

class TestEmail:
    def test_normalises_to_lowercase(self):
        e = Email(address="  USER@Example.COM  ")
        assert e.address == "user@example.com"

    def test_rejects_invalid_email(self):
        with pytest.raises(InvalidEmailError):
            Email(address="not-an-email")

    def test_equality_by_value(self):
        assert Email("a@b.com") == Email("A@B.COM")


class TestHashedPassword:
    def test_rejects_short_hash(self):
        with pytest.raises(InvalidPasswordError):
            HashedPassword(value="tooshort")

    def test_accepts_valid_hash(self):
        hp = HashedPassword(value=VALID_HASH)
        assert hp.value == VALID_HASH

    def test_matches_correct_hash(self):
        hp = HashedPassword(value=VALID_HASH)
        assert hp.matches(VALID_HASH) is True

    def test_rejects_wrong_hash(self):
        hp = HashedPassword(value=VALID_HASH)
        assert hp.matches("b" * 64) is False


class TestDeviceFingerprintValue:
    def test_rejects_non_hex(self):
        with pytest.raises(InvalidFingerprintError):
            DeviceFingerprintValue(raw="ZZZZ")

    def test_accepts_valid_hex(self):
        fp = DeviceFingerprintValue(raw="a" * 64)
        assert fp.raw == "a" * 64

    def test_normalises_to_lowercase(self):
        fp = DeviceFingerprintValue(raw="A" * 64)
        assert fp.raw == "a" * 64


# ══════════════════════════════════════════════════════════
# USER AGGREGATE TESTS
# ══════════════════════════════════════════════════════════

class TestUserAuthentication:
    def test_new_user_can_authenticate(self):
        user = make_user()
        assert user.can_authenticate() is True

    def test_inactive_user_cannot_authenticate(self):
        user = make_user()
        user.is_active = False
        assert user.can_authenticate() is False

    def test_inactive_user_raises_on_assert(self):
        user = make_user()
        user.is_active = False
        with pytest.raises(AccountInactiveError):
            user.assert_can_authenticate()

    def test_account_locks_after_threshold(self):
        user = make_user()
        for _ in range(MAX_FAILED_ATTEMPTS):
            user.register_failed_attempt()
        assert user.is_locked is True
        with pytest.raises(AccountLockedError):
            user.assert_can_authenticate()

    def test_auto_unlock_after_lock_expires(self):
        user = make_user()
        user.lock_account()
        # Move locked_until to the past
        user.locked_until = utc_now() - timedelta(seconds=1)
        assert user.can_authenticate() is True
        assert user.is_locked is False

    def test_reset_failed_attempts(self):
        user = make_user()
        for _ in range(3):
            user.register_failed_attempt()
        user.reset_failed_attempts()
        assert user.failed_attempts == 0

    def test_unlock_account_clears_all_state(self):
        user = make_user()
        for _ in range(MAX_FAILED_ATTEMPTS):
            user.register_failed_attempt()
        user.unlock_account()
        assert user.is_locked is False
        assert user.failed_attempts == 0
        assert user.locked_until is None

    def test_can_create_session_mirrors_can_authenticate(self):
        user = make_user()
        assert user.can_create_session() is True
        user.is_active = False
        assert user.can_create_session() is False


class TestUserRoles:
    def test_new_user_has_user_role(self):
        user = make_user()
        assert user.has_role(RoleType.USER) is True

    def test_assign_role(self):
        user = make_user()
        user.assign_role(Role.vendor())
        assert user.has_role(RoleType.VENDOR) is True

    def test_duplicate_role_raises(self):
        user = make_user()
        with pytest.raises(RoleAlreadyAssignedError):
            user.assign_role(Role.user())

    def test_remove_role(self):
        user = make_user()
        user.assign_role(Role.vendor())
        user.remove_role(RoleType.VENDOR)
        assert user.has_role(RoleType.VENDOR) is False

    def test_remove_nonexistent_role_raises(self):
        user = make_user()
        with pytest.raises(RoleNotFoundError):
            user.remove_role(RoleType.ADMIN)

    def test_assert_has_role_raises_when_missing(self):
        user = make_user()
        with pytest.raises(UnauthorizedError):
            user.assert_has_role(RoleType.ADMIN)


# ══════════════════════════════════════════════════════════
# SESSION ENTITY TESTS
# ══════════════════════════════════════════════════════════

class TestSession:
    def test_new_session_is_valid(self):
        user = make_user()
        session = make_session(user)
        assert session.is_valid() is True
        assert session.status == SessionStatus.ACTIVE

    def test_revoke_makes_session_invalid(self):
        user = make_user()
        session = make_session(user)
        session.revoke()
        assert session.is_valid() is False
        assert session.status == SessionStatus.REVOKED

    def test_expire_makes_session_invalid(self):
        user = make_user()
        session = make_session(user)
        session.expire()
        assert session.is_valid() is False
        assert session.status == SessionStatus.EXPIRED

    def test_expired_ttl_detected_on_is_valid(self):
        user = make_user()
        session = make_session(user)
        session.expires_at = utc_now() - timedelta(seconds=1)
        assert session.is_valid() is False
        assert session.status == SessionStatus.EXPIRED

    def test_assert_valid_raises_on_revoked(self):
        user = make_user()
        session = make_session(user)
        session.revoke()
        with pytest.raises(SessionRevokedError):
            session.assert_valid()

    def test_assert_owned_by_raises_on_wrong_user(self):
        user = make_user()
        other_id = UserId.generate()
        session = make_session(user)
        with pytest.raises(SessionOwnershipError):
            session.assert_owned_by(other_id)

    def test_bind_device_idempotent_for_same_device(self):
        user = make_user()
        session = make_session(user)
        session.bind_device("device-abc")
        session.bind_device("device-abc")   # should not raise
        assert session.device_fingerprint_id == "device-abc"

    def test_bind_different_device_raises(self):
        user = make_user()
        session = make_session(user)
        session.bind_device("device-abc")
        with pytest.raises(DeviceBindingError):
            session.bind_device("device-xyz")

    def test_revoke_is_terminal_over_expire(self):
        user = make_user()
        session = make_session(user)
        session.revoke()
        session.expire()  # should be no-op — revoked is stronger
        assert session.status == SessionStatus.REVOKED

    def test_revoke_is_idempotent(self):
        user = make_user()
        session = make_session(user)
        session.revoke()
        session.revoke()  # should not raise
        assert session.status == SessionStatus.REVOKED


# ══════════════════════════════════════════════════════════
# DEVICE FINGERPRINT ENTITY TESTS
# ══════════════════════════════════════════════════════════

class TestDeviceFingerprint:
    def test_new_device_is_untrusted(self):
        user = make_user()
        fp = DeviceFingerprint.create(
            user_id=user.id,
            fingerprint=make_fingerprint_value(),
            user_agent="Mozilla/5.0",
            ip_address="1.2.3.4",
        )
        assert fp.is_trusted is False
        assert fp.is_known is False
        assert fp.is_flagged is False

    def test_mark_seen_sets_known(self):
        user = make_user()
        fp = DeviceFingerprint.create(
            user_id=user.id,
            fingerprint=make_fingerprint_value(),
            user_agent="Mozilla/5.0",
            ip_address="1.2.3.4",
        )
        fp.mark_seen()
        assert fp.is_known is True

    def test_flag_suspicious_revokes_trust(self):
        user = make_user()
        fp = DeviceFingerprint.create(
            user_id=user.id,
            fingerprint=make_fingerprint_value(),
            user_agent="Mozilla/5.0",
            ip_address="1.2.3.4",
        )
        fp.promote_trust()
        fp.flag_suspicious()
        assert fp.is_flagged is True
        assert fp.is_trusted is False

    def test_flagged_device_cannot_be_trusted(self):
        user = make_user()
        fp = DeviceFingerprint.create(
            user_id=user.id,
            fingerprint=make_fingerprint_value(),
            user_agent="Mozilla/5.0",
            ip_address="1.2.3.4",
        )
        fp.flag_suspicious()
        with pytest.raises(ValueError):
            fp.promote_trust()

    def test_belongs_to_correct_user(self):
        user = make_user()
        fp = DeviceFingerprint.create(
            user_id=user.id,
            fingerprint=make_fingerprint_value(),
            user_agent="Mozilla/5.0",
            ip_address="1.2.3.4",
        )
        assert fp.belongs_to(user.id) is True
        assert fp.belongs_to(UserId.generate()) is False


# ══════════════════════════════════════════════════════════
# REFRESH TOKEN ENTITY TESTS
# ══════════════════════════════════════════════════════════

class TestRefreshToken:
    def test_root_token_is_active(self):
        user = make_user()
        session = make_session(user)
        token = RefreshToken.create_root(session_id=session.id, user_id=user.id)
        assert token.is_valid() is True
        assert token.status == TokenStatus.ACTIVE
        assert token.parent_token_id is None

    def test_rotation_produces_successor(self):
        user = make_user()
        session = make_session(user)
        root = RefreshToken.create_root(session_id=session.id, user_id=user.id)
        successor = RefreshToken.rotate(parent=root)
        assert root.status == TokenStatus.USED
        assert successor.status == TokenStatus.ACTIVE
        assert successor.parent_token_id == root.id
        assert str(successor.family_id) == str(root.family_id)

    def test_reuse_raises(self):
        user = make_user()
        session = make_session(user)
        root = RefreshToken.create_root(session_id=session.id, user_id=user.id)
        RefreshToken.rotate(parent=root)
        with pytest.raises(TokenReuseDetectedError):
            RefreshToken.rotate(parent=root)   # reuse!

    def test_expired_token_raises(self):
        user = make_user()
        session = make_session(user)
        token = RefreshToken.create_root(session_id=session.id, user_id=user.id)
        token.expires_at = utc_now() - timedelta(seconds=1)
        with pytest.raises(TokenExpiredError):
            RefreshToken.rotate(parent=token)

    def test_invalidate_family_marks_compromised(self):
        user = make_user()
        session = make_session(user)
        token = RefreshToken.create_root(session_id=session.id, user_id=user.id)
        token.invalidate_family()
        assert token.family_compromised is True
        assert token.status == TokenStatus.REVOKED
        with pytest.raises(TokenFamilyCompromisedError):
            RefreshToken.rotate(parent=token)

    def test_detect_reuse_on_used_token(self):
        user = make_user()
        session = make_session(user)
        root = RefreshToken.create_root(session_id=session.id, user_id=user.id)
        RefreshToken.rotate(parent=root)
        assert root.detect_reuse() is True


# ══════════════════════════════════════════════════════════
# LOGIN ACTIVITY TESTS
# ══════════════════════════════════════════════════════════

class TestLoginActivity:
    def test_success_record(self):
        user = make_user()
        session = make_session(user)
        act = LoginActivity.record_success(
            user_id=user.id,
            session_id=session.id,
            ip_address="1.2.3.4",
            user_agent="Agent",
        )
        assert act.was_successful is True
        assert act.outcome == LoginOutcome.SUCCESS

    def test_failure_record_requires_reason(self):
        with pytest.raises(ValueError):
            LoginActivity.record_failure(
                user_id=None, ip_address="1.2.3.4",
                user_agent="Agent", failure_reason=""
            )

    def test_blocked_record(self):
        user = make_user()
        act = LoginActivity.record_blocked(
            user_id=user.id,
            ip_address="1.2.3.4",
            user_agent="Agent",
            failure_reason="Account locked.",
        )
        assert act.was_blocked is True

    def test_login_activity_is_immutable(self):
        user = make_user()
        session = make_session(user)
        act = LoginActivity.record_success(
            user_id=user.id, session_id=session.id,
            ip_address="1.2.3.4", user_agent="Agent",
        )
        with pytest.raises(Exception):   # frozen dataclass
            act.outcome = LoginOutcome.FAILURE


# ══════════════════════════════════════════════════════════
# AUTHENTICATION SERVICE TESTS
# ══════════════════════════════════════════════════════════

class TestAuthenticationService:
    def setup_method(self):
        self.service = AuthenticationService()

    def test_successful_authentication(self):
        user = make_user()
        result = self.service.authenticate(
            user=user,
            presented_password_hash=VALID_HASH,
            ip_address="1.2.3.4",
            user_agent="TestAgent",
        )
        assert result.succeeded is True
        assert result.session is not None
        assert result.activity.was_successful is True

    def test_wrong_password_returns_failure(self):
        user = make_user()
        result = self.service.authenticate(
            user=user,
            presented_password_hash="b" * 64,
            ip_address="1.2.3.4",
            user_agent="TestAgent",
        )
        assert result.succeeded is False
        assert result.was_blocked is False
        assert user.failed_attempts == 1

    def test_inactive_account_returns_blocked(self):
        user = make_user()
        user.is_active = False
        result = self.service.authenticate(
            user=user,
            presented_password_hash=VALID_HASH,
            ip_address="1.2.3.4",
            user_agent="TestAgent",
        )
        assert result.succeeded is False
        assert result.was_blocked is True

    def test_locked_account_returns_blocked(self):
        user = make_user()
        user.lock_account()
        result = self.service.authenticate(
            user=user,
            presented_password_hash=VALID_HASH,
            ip_address="1.2.3.4",
            user_agent="TestAgent",
        )
        assert result.succeeded is False
        assert result.was_blocked is True

    def test_success_creates_device_fingerprint(self):
        user = make_user()
        fp_value = make_fingerprint_value()
        result = self.service.authenticate(
            user=user,
            presented_password_hash=VALID_HASH,
            ip_address="1.2.3.4",
            user_agent="TestAgent",
            device_fingerprint_value=fp_value,
        )
        assert result.succeeded is True
        assert result.device is not None
        assert result.session.device_fingerprint_id == result.device.id

    def test_lock_after_max_failures(self):
        user = make_user()
        for _ in range(MAX_FAILED_ATTEMPTS):
            self.service.authenticate(
                user=user,
                presented_password_hash="b" * 64,
                ip_address="1.2.3.4",
                user_agent="TestAgent",
            )
        assert user.is_locked is True

    def test_validate_session_valid(self):
        user = make_user()
        session = make_session(user)
        result = self.service.validate_session(session, user.id)
        assert result.valid is True

    def test_validate_session_wrong_user(self):
        user = make_user()
        session = make_session(user)
        result = self.service.validate_session(session, UserId.generate())
        assert result.valid is False

    def test_validate_session_device_mismatch(self):
        user = make_user()
        session = make_session(user)
        session.bind_device("device-abc")
        result = self.service.validate_session(
            session, user.id, presented_device_fingerprint_id="device-xyz"
        )
        assert result.valid is False


# ══════════════════════════════════════════════════════════
# SESSION SERVICE TESTS
# ══════════════════════════════════════════════════════════

class TestSessionService:
    def setup_method(self):
        self.service = SessionService()

    def test_revoke_session(self):
        user = make_user()
        session = make_session(user)
        self.service.revoke_session(session, user.id)
        assert session.status == SessionStatus.REVOKED

    def test_revoke_all_user_sessions(self):
        user = make_user()
        sessions = [make_session(user) for _ in range(3)]
        count = self.service.revoke_all_user_sessions(sessions, user.id)
        assert count == 3
        assert all(s.status == SessionStatus.REVOKED for s in sessions)

    def test_revoke_all_except_keeps_one(self):
        user = make_user()
        sessions = [make_session(user) for _ in range(3)]
        keep = sessions[1]
        count = self.service.revoke_all_except(sessions, user.id, str(keep.id))
        assert count == 2
        assert keep.status == SessionStatus.ACTIVE

    def test_detect_device_anomaly_on_mismatch(self):
        user = make_user()
        session = make_session(user)
        fp_value = make_fingerprint_value()
        device = DeviceFingerprint.create(
            user_id=user.id,
            fingerprint=fp_value,
            user_agent="Mozilla",
            ip_address="1.2.3.4",
        )
        session.bind_device(device.id)
        other_fp = DeviceFingerprintValue(raw="b" * 64)
        result = self.service.detect_device_anomaly(session, other_fp, device)
        assert result.anomaly_detected is True


# ══════════════════════════════════════════════════════════
# TOKEN SERVICE TESTS
# ══════════════════════════════════════════════════════════

class TestTokenService:
    def setup_method(self):
        self.service = TokenService()

    def test_issue_root_token(self):
        user = make_user()
        session = make_session(user)
        token = self.service.issue_root_token(session, user.id)
        assert token.is_valid() is True

    def test_rotate_token(self):
        user = make_user()
        session = make_session(user)
        root = self.service.issue_root_token(session, user.id)
        result = self.service.rotate_token(root, session)
        assert result.old_token.status == TokenStatus.USED
        assert result.new_token.status == TokenStatus.ACTIVE

    def test_reuse_detected(self):
        user = make_user()
        session = make_session(user)
        root = self.service.issue_root_token(session, user.id)
        self.service.rotate_token(root, session)
        assert self.service.detect_reuse(root) is True

    def test_handle_reuse_revokes_session(self):
        user = make_user()
        session = make_session(user)
        root = self.service.issue_root_token(session, user.id)
        r = self.service.rotate_token(root, session)
        result = self.service.handle_reuse_detected(
            reused_token=root,
            all_family_tokens=[root, r.new_token],
            session=session,
        )
        assert result.session_revoked is True
        assert session.status == SessionStatus.REVOKED
        assert len(result.tokens_revoked) >= 1

    def test_invalidate_token_family(self):
        user = make_user()
        session = make_session(user)
        root = self.service.issue_root_token(session, user.id)
        r = self.service.rotate_token(root, session)
        count = self.service.invalidate_token_family(
            str(root.family_id), [root, r.new_token]
        )
        assert count == 2
        assert root.family_compromised is True
        assert r.new_token.family_compromised is True


if __name__ == "__main__":
    pytest.main([__file__, "-v", "--tb=short"])