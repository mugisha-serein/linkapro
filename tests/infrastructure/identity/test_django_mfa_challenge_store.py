import uuid
from datetime import timedelta

from django.core.cache import cache

from application.identity.shared.ports import MfaEnrollmentState
from domain.identity.mfa import MfaMethod, MfaPolicy
from domain.identity.shared import SystemClock
from domain.identity.verification import VerificationCode
from infrastructure.identity.django_mfa_challenge_store import DjangoMfaEnrollmentStore, _enrollment_key, _replay_key


def test_mfa_enrollment_store_round_trips_typed_state():
    cache.clear()
    user_id = uuid.uuid4()
    now = SystemClock().now()
    challenge = MfaPolicy(challenge_ttl=timedelta(minutes=10)).issue_challenge(
        user_id=user_id,
        method=MfaMethod.TOTP,
        now=now,
    )
    state = MfaEnrollmentState(challenge=challenge, secret="setup-secret")
    store = DjangoMfaEnrollmentStore()

    store.save(state, ttl=600)
    cached_value = cache.get(_enrollment_key(user_id))
    loaded = store.get(user_id)

    assert isinstance(cached_value, dict)
    assert loaded == state


def test_mfa_enrollment_store_deserializes_legacy_secret_string():
    cache.clear()
    user_id = uuid.uuid4()
    cache.set(_enrollment_key(user_id), "legacy-secret", timeout=600)

    loaded = DjangoMfaEnrollmentStore().get(user_id)

    assert isinstance(loaded, MfaEnrollmentState)
    assert loaded.secret == "legacy-secret"
    assert loaded.challenge.user_id == user_id
    assert loaded.challenge.method is MfaMethod.TOTP


def test_mfa_replay_key_uses_hmac_fingerprint_not_raw_code(settings):
    settings.MFA_REPLAY_HMAC_KEY = "test-mfa-replay-hmac-key"
    challenge_id = uuid.uuid4()
    code = "123456"

    key = _replay_key(challenge_id, VerificationCode(code))

    assert key.startswith(f"mfa-replay:{challenge_id}:")
    assert code not in key
    assert "totp_used" not in key
    assert len(key.rsplit(":", 1)[-1]) == 64
