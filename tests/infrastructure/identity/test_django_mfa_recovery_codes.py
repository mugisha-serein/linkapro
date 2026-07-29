import uuid

import pytest
from django.core.cache import cache

from domain.identity.mfa import RecoveryCode
from infrastructure.identity.django_mfa_recovery_codes import (
    DjangoMfaRecoveryCodeRepository,
    HmacRecoveryCodeHasher,
    SecureRecoveryCodeGenerator,
)


pytestmark = pytest.mark.django_db


def test_recovery_code_repository_stores_hashes_without_plaintext(settings):
    settings.MFA_RECOVERY_CODE_HASH_KEY = "test-recovery-code-hash-key"
    cache.clear()
    user_id = uuid.uuid4()
    plaintext_code = "abcd-efgh"
    code_hash = HmacRecoveryCodeHasher().hash_recovery_code(plaintext_code)
    repository = DjangoMfaRecoveryCodeRepository()

    repository.replace_for_user(
        user_id,
        (RecoveryCode(id=uuid.UUID(int=1), code_hash=code_hash),),
    )

    loaded = repository.get_for_user(user_id)
    assert loaded[0].code_hash == code_hash
    assert plaintext_code not in repr(loaded)


def test_secure_recovery_code_generator_returns_different_codes():
    generator = SecureRecoveryCodeGenerator()

    first = generator.generate()
    second = generator.generate()

    assert first != second
    assert "-" in first
