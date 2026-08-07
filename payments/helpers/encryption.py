import base64
import json

from payments.domain.value_objects import EncryptedField

ENCRYPTED_FIELD_KEYS = frozenset({"ciphertext", "iv", "tag", "dek_encrypted"})


def is_encrypted_payload(value: object) -> bool:
    """Return True when the value is a JSON-shaped encrypted-field payload."""
    return isinstance(value, dict) and ENCRYPTED_FIELD_KEYS.issubset(value.keys())


def encrypted_field_to_json(ef: EncryptedField) -> dict:
    return {
        "ciphertext": base64.b64encode(ef.ciphertext).decode('ascii'),
        "iv": base64.b64encode(ef.iv).decode('ascii'),
        "tag": base64.b64encode(ef.tag).decode('ascii'),
        "dek_encrypted": base64.b64encode(ef.dek_encrypted).decode('ascii'),
    }

def encrypted_field_from_json(data: dict) -> EncryptedField:
    return EncryptedField(
        ciphertext=base64.b64decode(data["ciphertext"]),
        iv=base64.b64decode(data["iv"]),
        tag=base64.b64decode(data["tag"]),
        dek_encrypted=base64.b64decode(data["dek_encrypted"]),
    )