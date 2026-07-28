import uuid

from domain.identity.verification import VerificationCode
from infrastructure.identity.django_mfa_challenge_store import _replay_key


def test_mfa_replay_key_uses_hmac_fingerprint_not_raw_code(settings):
    settings.MFA_REPLAY_HMAC_KEY = "test-mfa-replay-hmac-key"
    challenge_id = uuid.uuid4()
    code = "123456"

    key = _replay_key(challenge_id, VerificationCode(code))

    assert key.startswith(f"mfa-replay:{challenge_id}:")
    assert code not in key
    assert "totp_used" not in key
    assert len(key.rsplit(":", 1)[-1]) == 64
