import secrets
from cryptography.hazmat.primitives.ciphers.aead import AESGCM
from payments.domain.value_objects import EncryptedField


def encrypt_field(plaintext: bytes, dek: bytes) -> EncryptedField:
    """Encrypt a field using AES-256-GCM with a DEK."""
    iv = secrets.token_bytes(12)
    aesgcm = AESGCM(dek)
    ciphertext = aesgcm.encrypt(iv, plaintext, None)
    # ciphertext includes the tag at the end (last 16 bytes)
    tag = ciphertext[-16:]
    actual_ciphertext = ciphertext[:-16]
    return EncryptedField(
        ciphertext=actual_ciphertext,
        iv=iv,
        tag=tag,
        dek_encrypted=b"",  # to be filled by repository
    )


def decrypt_field(encrypted: EncryptedField, dek: bytes) -> bytes:
    """Decrypt a field using AES-256-GCM."""
    aesgcm = AESGCM(dek)
    ciphertext_with_tag = encrypted.ciphertext + encrypted.tag
    return aesgcm.decrypt(encrypted.iv, ciphertext_with_tag, None)