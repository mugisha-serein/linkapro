import uuid

from django.core.cache import cache

from domain.identity.verification import VerificationCode, VerificationPolicy, VerificationPurpose
from infrastructure.identity.django_verification_challenge_repository import (
    DjangoVerificationChallengeRepository,
    _verification_challenge_key,
)


def test_django_verification_challenge_repository_round_trips_challenge():
    cache.clear()
    challenge = VerificationPolicy().issue_challenge(
        user_id=uuid.uuid4(),
        purpose=VerificationPurpose.EMAIL,
        code=VerificationCode("code"),
    )
    challenge.pull_events()
    challenge.failed_attempts = 2
    repository = DjangoVerificationChallengeRepository()

    repository.save(challenge)
    cached_value = cache.get(_verification_challenge_key(challenge.id))
    loaded = repository.get(challenge.id)

    assert isinstance(cached_value, dict)
    assert loaded.id == challenge.id
    assert loaded.user_id == challenge.user_id
    assert loaded.purpose is VerificationPurpose.EMAIL
    assert loaded.code_digest == challenge.code_digest
    assert loaded.failed_attempts == 2
    assert loaded.expires_at == challenge.expires_at
