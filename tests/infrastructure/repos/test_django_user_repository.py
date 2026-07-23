import uuid
import pytest
from datetime import datetime

from domain.identity.entities import User, UserRole
from domain.identity.value_objects import Email, PasswordHash, TOTPSecret
from infrastructure.repos.django_user_repository import DjangoUserRepository
from django_app.identity.models import User as DjangoUser


class _KeyProvider:
    def wrap_dek(self, dek: bytes) -> bytes:
        return dek

    def unwrap_dek(self, encrypted_dek: bytes) -> bytes:
        return encrypted_dek


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
        domain_user.mark_verified()
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

    def test_totp_secret_is_encrypted_at_rest(self):
        repo = DjangoUserRepository(key_provider=_KeyProvider())
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
        assert stored_user.totp_secret["ciphertext"] != "JBSWY3DPEHPK3PXP"
        assert repo.get_totp_secret(domain_user.id).reveal_for_totp_verification() == "JBSWY3DPEHPK3PXP"
