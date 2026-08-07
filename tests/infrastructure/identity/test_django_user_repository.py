import uuid
import pytest
from datetime import datetime

from domain.identity.account import User, UserRole
from domain.identity.credentials import Email, PasswordHash
from domain.identity.mfa import TOTPSecret
from domain.identity.verification import VerificationCode, VerificationPolicy, VerificationPurpose
from infrastructure.identity.django_user_repository import DjangoUserRepository
from interface.identity.models import User as DjangoUser


class _KeyProvider:
    """Stateless stand-in for the Vault-backed envelope key provider.

    Stateless on purpose: any instance can unwrap a DEK wrapped by any other
    instance, which mirrors how different repository instances (the test
    fixture vs. the view factory) must interoperate in the integration tests.
    """

    _PREFIX = b"wrapped:"

    def wrap_dek(self, dek):
        return self._PREFIX + dek

    def unwrap_dek(self, wrapped):
        return wrapped[len(self._PREFIX):]


def _succeeded_email_challenge(user_id: uuid.UUID):
    code = VerificationCode("123456")
    challenge = VerificationPolicy().issue_challenge(
        user_id=user_id,
        purpose=VerificationPurpose.EMAIL,
        code=code,
    )
    VerificationPolicy().verify_challenge(challenge, code)
    challenge.pull_events()
    return challenge


@pytest.mark.django_db
class TestDjangoUserRepository:
    def test_save_and_retrieve(self):
        repo = DjangoUserRepository()
        domain_user = User(
            id=uuid.uuid4(),
            email=Email("test@example.com"),
            password_hash=PasswordHash("hashed_secret"),
            first_name="Test",
            last_name="User",
            role=UserRole.PLANNER,
        )
        saved = repo.save(domain_user)

        assert saved.id == domain_user.id
        assert DjangoUser.objects.count() == 1

        retrieved = repo.get_by_id(domain_user.id)
        assert retrieved is not None
        assert str(retrieved.email) == "test@example.com"

    def test_get_by_email(self):
        repo = DjangoUserRepository()
        email = Email("findme@example.com")
        domain_user = User(
            id=uuid.uuid4(),
            email=email,
            password_hash=PasswordHash("hash"),
            first_name="Find",
            last_name="Me",
            role=UserRole.VENDOR,
        )
        repo.save(domain_user)

        found = repo.get_by_email(email)
        assert found is not None
        assert found.first_name == "Find"

    def test_get_by_email_matches_existing_mixed_case_email(self):
        repo = DjangoUserRepository()
        django_user = DjangoUser.objects.create(
            email="MixedCase.User@example.com",
            first_name="Mixed",
            last_name="Case",
            role="vendor",
            is_active=True,
            is_verified=True,
        )
        django_user.set_password("StrongPass1!")
        django_user.save()

        found = repo.get_by_email(Email("mixedcase.user@example.com"))

        assert found is not None
        assert found.id == django_user.id
        assert str(found.email) == "mixedcase.user@example.com"

    def test_update_existing(self):
        repo = DjangoUserRepository()
        domain_user = User(
            id=uuid.uuid4(),
            email=Email("update@example.com"),
            password_hash=PasswordHash("old"),
            first_name="Old",
            last_name="Name",
            role=UserRole.PLANNER,
        )
        repo.save(domain_user)

        # modify
        domain_user.first_name = "New"
        domain_user.mark_verified(challenge=_succeeded_email_challenge(domain_user.id))
        repo.save(domain_user)

        updated = repo.get_by_id(domain_user.id)
        assert updated.first_name == "New"
        assert updated.is_verified is True

    def test_delete(self):
        repo = DjangoUserRepository()
        domain_user = User(
            id=uuid.uuid4(),
            email=Email("delete@example.com"),
            password_hash=PasswordHash("hash"),
            first_name="Delete",
            last_name="Me",
            role=UserRole.PLANNER,
        )
        repo.save(domain_user)
        repo.delete(domain_user.id)

        assert repo.get_by_id(domain_user.id) is None

    def test_totp_secret_round_trips_encrypted_through_repository(self):
        key_provider = _KeyProvider()
        repo = DjangoUserRepository(key_provider=key_provider)
        domain_user = User(
            id=uuid.uuid4(),
            email=Email("mfa@example.com"),
            password_hash=PasswordHash("hash"),
            first_name="Mfa",
            last_name="User",
            role=UserRole.PLANNER,
        )
        repo.save(domain_user)

        repo.set_totp_secret(domain_user.id, TOTPSecret("JBSWY3DPEHPK3PXP"))

        stored_user = DjangoUser.objects.get(id=domain_user.id)
        assert stored_user.totp_secret != "JBSWY3DPEHPK3PXP"
        assert "JBSWY3DPEHPK3PXP" not in stored_user.totp_secret
        assert repo.get_totp_secret(domain_user.id).reveal_for_totp_verification() == "JBSWY3DPEHPK3PXP"

        # A fresh repository using the same key provider decrypts the stored value.
        fresh_repo = DjangoUserRepository(key_provider=key_provider)
        assert fresh_repo.get_totp_secret(domain_user.id).reveal_for_totp_verification() == "JBSWY3DPEHPK3PXP"

    def test_get_totp_secret_accepts_legacy_plaintext_value(self):
        repo = DjangoUserRepository(key_provider=_KeyProvider())
        django_user = DjangoUser.objects.create(
            email="legacy-totp@example.com",
            first_name="Legacy",
            last_name="Totp",
            role="planner",
            is_active=True,
            is_verified=True,
            totp_secret="JBSWY3DPEHPK3PXP",
            two_factor_enabled=True,
        )

        secret = repo.get_totp_secret(django_user.id)

        assert secret is not None
        assert secret.reveal_for_totp_verification() == "JBSWY3DPEHPK3PXP"

    def test_get_totp_secret_returns_none_for_corrupt_payload(self):
        repo = DjangoUserRepository(key_provider=_KeyProvider())
        django_user = DjangoUser.objects.create(
            email="corrupt-totp@example.com",
            first_name="Corrupt",
            last_name="Totp",
            role="planner",
            is_active=True,
            is_verified=True,
            totp_secret='{"ciphertext":"!!!","iv":"!!!","tag":"!!!","dek_encrypted":"!!!"}',
            two_factor_enabled=True,
        )

        assert repo.get_totp_secret(django_user.id) is None

    def test_get_totp_secret_returns_none_for_unrecognized_value(self):
        repo = DjangoUserRepository(key_provider=_KeyProvider())
        django_user = DjangoUser.objects.create(
            email="garbage-totp@example.com",
            first_name="Garbage",
            last_name="Totp",
            role="planner",
            is_active=True,
            is_verified=True,
            totp_secret="not-a-real-secret",
            two_factor_enabled=True,
        )

        assert repo.get_totp_secret(django_user.id) is None

    def test_clear_totp_secret_removes_encrypted_value(self):
        key_provider = _KeyProvider()
        repo = DjangoUserRepository(key_provider=key_provider)
        domain_user = User(
            id=uuid.uuid4(),
            email=Email("mfa-clear@example.com"),
            password_hash=PasswordHash("hash"),
            first_name="Mfa",
            last_name="Clear",
            role=UserRole.PLANNER,
        )
        repo.save(domain_user)
        repo.set_totp_secret(domain_user.id, TOTPSecret("JBSWY3DPEHPK3PXP"))
        assert repo.get_totp_secret(domain_user.id) is not None

        repo.clear_totp_secret(domain_user.id)

        stored_user = DjangoUser.objects.get(id=domain_user.id)
        assert stored_user.totp_secret is None
        assert stored_user.two_factor_enabled is False
        assert repo.get_totp_secret(domain_user.id) is None
