import base64
import logging
from typing import Optional
import requests
from django.conf import settings
from tenacity import retry, stop_after_attempt, wait_exponential, retry_if_exception_type

from payments.application.ports import IKeyProvider
from payments.application.exceptions import InfrastructureUnavailableError, KeyProviderError

logger = logging.getLogger(__name__)


class VaultKeyProvider(IKeyProvider):
    """HashiCorp Vault Transit engine key provider."""

    def __init__(self):
        self.vault_addr = settings.VAULT_ADDR.rstrip('/')
        self.role_id = settings.VAULT_ROLE_ID
        self.secret_id = settings.VAULT_SECRET_ID
        self.transit_key = settings.VAULT_TRANSIT_KEY_NAME
        self._token: Optional[str] = None

    def _authenticate(self) -> str:
        """Authenticate with Vault using AppRole and return a token."""
        url = f"{self.vault_addr}/v1/auth/approle/login"
        payload = {"role_id": self.role_id, "secret_id": self.secret_id}
        try:
            response = requests.post(url, json=payload, timeout=10)
            response.raise_for_status()
            data = response.json()
            return data["auth"]["client_token"]
        except (requests.RequestException, KeyError) as e:
            logger.error("Vault authentication failed: %s", e)
            raise InfrastructureUnavailableError("Vault authentication failed") from e

    def _get_token(self) -> str:
        """Get a valid token, refreshing if needed."""
        if self._token is None:
            self._token = self._authenticate()
        return self._token

    def _make_request(self, method: str, path: str, json_data: dict) -> dict:
        token = self._get_token()
        url = f"{self.vault_addr}/v1/{path}"
        headers = {"X-Vault-Token": token}
        try:
            response = requests.request(method, url, headers=headers, json=json_data, timeout=15)
            response.raise_for_status()
            return response.json()
        except requests.HTTPError as e:
            if response.status_code == 403:
                # Token may be expired; clear and retry once
                self._token = None
                token = self._get_token()
                headers["X-Vault-Token"] = token
                response = requests.request(method, url, headers=headers, json=json_data, timeout=15)
                response.raise_for_status()
                return response.json()
            raise
        except requests.RequestException as e:
            raise InfrastructureUnavailableError(f"Vault request failed: {e}") from e

    @retry(
        stop=stop_after_attempt(3),
        wait=wait_exponential(multiplier=1, min=1, max=5),
        retry=retry_if_exception_type(InfrastructureUnavailableError),
        reraise=True,
    )
    def wrap_dek(self, dek: bytes) -> bytes:
        """Encrypt DEK using Vault transit."""
        plaintext_b64 = base64.b64encode(dek).decode('ascii')
        path = f"transit/encrypt/{self.transit_key}"
        payload = {"plaintext": plaintext_b64}
        data = self._make_request("POST", path, payload)
        ciphertext = data["data"]["ciphertext"]
        return ciphertext.encode('ascii')

    @retry(
        stop=stop_after_attempt(3),
        wait=wait_exponential(multiplier=1, min=1, max=5),
        retry=retry_if_exception_type(InfrastructureUnavailableError),
        reraise=True,
    )
    def unwrap_dek(self, encrypted_dek: bytes) -> bytes:
        """Decrypt DEK using Vault transit."""
        ciphertext = encrypted_dek.decode('ascii')
        path = f"transit/decrypt/{self.transit_key}"
        payload = {"ciphertext": ciphertext}
        data = self._make_request("POST", path, payload)
        plaintext_b64 = data["data"]["plaintext"]
        return base64.b64decode(plaintext_b64)