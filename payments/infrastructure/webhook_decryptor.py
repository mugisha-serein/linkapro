import base64
import json
import logging
from Crypto.Cipher import DES3
from Crypto.Util.Padding import unpad
from django.conf import settings

from payments.application.ports import IWebhookDecryptor
from payments.domain.webhook_crypto import DecryptionResult

logger = logging.getLogger(__name__)


class FlutterwaveWebhookDecryptor(IWebhookDecryptor):
    def __init__(self):
        self.encryption_key = settings.FLW_ENCRYPTION_KEY.encode()  # 24-byte 3DES key

    def decrypt(self, base64_payload: str) -> DecryptionResult:
        try:
            # Flutterwave sends encrypted payload as Base64 string
            ciphertext = base64.b64decode(base64_payload)
            if len(ciphertext) < 8:
                return DecryptionResult(success=False, error="Invalid ciphertext length")

            # 3DES-CBC: IV is first 8 bytes, ciphertext follows
            iv = ciphertext[:8]
            encrypted_data = ciphertext[8:]

            cipher = DES3.new(self.encryption_key, DES3.MODE_CBC, iv=iv)
            plaintext = unpad(cipher.decrypt(encrypted_data), 8)
            payload = json.loads(plaintext.decode('utf-8'))
            return DecryptionResult(success=True, decrypted_data=payload)

        except Exception as e:
            logger.error("Webhook decryption failed: %s", str(e))
            return DecryptionResult(success=False, error="Decryption failed")