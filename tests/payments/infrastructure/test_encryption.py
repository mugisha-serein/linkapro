import secrets
import json
from payments.infrastructure.crypto import (
    encrypt_field,
    decrypt_field,
)
from payments.helpers.encryption import encrypted_field_to_json, encrypted_field_from_json
from payments.domain.value_objects import EncryptedField


def test_encrypt_decrypt_roundtrip():
    dek = secrets.token_bytes(32)
    plaintext = b"sensitive payment data"

    # Encrypt
    ef = encrypt_field(plaintext, dek)

    # Build final EncryptedField with wrapped DEK (simulate repository step)
    wrapped_dek = b"fake_wrapped_dek"
    ef_with_dek = EncryptedField(
        ciphertext=ef.ciphertext,
        iv=ef.iv,
        tag=ef.tag,
        dek_encrypted=wrapped_dek,
    )

    # Serialize to JSON (as done in repository)
    serialized = encrypted_field_to_json(ef_with_dek)

    # Deserialize back
    ef_restored = encrypted_field_from_json(serialized)

    # Decrypt (using original DEK, as unwrapped by Vault)
    decrypted = decrypt_field(ef_restored, dek)
    assert decrypted == plaintext


def test_encrypt_field_produces_valid_gcm():
    dek = secrets.token_bytes(32)
    plaintext = b"hello world"
    ef = encrypt_field(plaintext, dek)

    assert len(ef.iv) == 12
    assert len(ef.tag) == 16
    assert len(ef.ciphertext) == len(plaintext)
    assert ef.dek_encrypted == b""  # not set by encrypt_field


def test_encrypted_field_json_roundtrip():
    original = EncryptedField(
        ciphertext=b"cipher",
        iv=b"123456789012",
        tag=b"1234567890123456",
        dek_encrypted=b"wrapped",
    )
    serialized = encrypted_field_to_json(original)
    restored = encrypted_field_from_json(serialized)
    assert restored == original