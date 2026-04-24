import json
from jwcrypto import jwk, jwe
from django.conf import settings


class JweEnvelopeAdapter:
    def __init__(self):
        self._private_key = None

    @property
    def private_key(self):
        if self._private_key is None:
            key_data = settings.JWE_PRIVATE_KEY
            self._private_key = jwk.JWK.from_pem(key_data.encode('utf-8'))
        return self._private_key

    def get_public_jwk(self) -> dict:
        return self.private_key.export(as_dict=True, private_key=False)

    def decrypt_request(self, jwe_compact: str) -> dict:
        """Decrypt a JWE compact serialization and return the plaintext dictionary."""
        try:
            token = jwe.JWE()
            # Pass key directly – this is the standard approach
            token.deserialize(jwe_compact, key=self.private_key)
            plaintext = token.payload.decode('utf-8')
            return json.loads(plaintext)
        except Exception as e:
            raise ValueError("JWE decryption failed") from e

    def encrypt_response(self, payload: dict, recipient_public_jwk: dict) -> str:
        try:
            public_key = jwk.JWK(**recipient_public_jwk)
            protected = {"alg": "ECDH-ES+A256KW", "enc": "A256GCM", "typ": "JWE"}
            token = jwe.JWE(plaintext=json.dumps(payload).encode('utf-8'),
                            protected=protected)
            token.add_recipient(public_key)
            return token.serialize(compact=True)
        except Exception as e:
            raise ValueError("JWE encryption failed") from e