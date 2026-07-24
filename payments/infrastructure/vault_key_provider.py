import base64
import binascii
import logging
import os
import threading
import time
from pathlib import Path
from typing import Optional
import requests
from django.conf import settings
from django.core.exceptions import ImproperlyConfigured
from tenacity import retry, stop_after_attempt, wait_exponential, retry_if_exception_type

from payments.application.ports import IKeyProvider
from payments.application.exceptions import InfrastructureUnavailableError, KeyProviderError

logger = logging.getLogger(__name__)


def _config_value(name: str, default: str = "") -> str:
    value = getattr(settings, name, None)
    if value is None or str(value).strip() == "":
        value = os.environ.get(name, default)
    return str(value or "").strip()


def _file_config_value(name: str) -> str:
    path = _config_value(f"{name}_FILE")
    if not path:
        return _config_value(name)
    try:
        return Path(path).read_text(encoding="utf-8").strip()
    except OSError as exc:
        raise ImproperlyConfigured(f"{name}_FILE could not be read") from exc


def _response_mentions_sealed(data: object) -> bool:
    if not isinstance(data, dict):
        return False
    errors = data.get("errors")
    if not isinstance(errors, list):
        return False
    return any("sealed" in str(error).lower() for error in errors)


class VaultKeyProvider(IKeyProvider):
    """HashiCorp Vault Transit engine key provider."""

    def __init__(self):
        self.vault_addr = _config_value("VAULT_ADDR").rstrip('/')
        self.role_id = _file_config_value("VAULT_ROLE_ID")
        self.secret_id = _file_config_value("VAULT_SECRET_ID")
        self.transit_key = _config_value("VAULT_TRANSIT_KEY_NAME", "linkapro-payments-kek")
        self.namespace = _config_value("VAULT_NAMESPACE")
        self.session = requests.Session()
        self.session.headers.update(
            {
                "Accept": "application/json",
                "Content-Type": "application/json",
            }
        )
        if self.namespace:
            self.session.headers["X-Vault-Namespace"] = self.namespace
        self.token_renewal_margin_seconds = int(_config_value("VAULT_TOKEN_RENEWAL_MARGIN_SECONDS", "60"))
        self._token_lock = threading.RLock()
        self._token: Optional[str] = None
        self._token_expires_at: float = 0.0

    def _authenticate(self) -> tuple[str, float]:
        """Authenticate with Vault using AppRole and return a token."""
        url = f"{self.vault_addr}/v1/auth/approle/login"
        payload = {"role_id": self.role_id, "secret_id": self.secret_id}
        data = self._send("POST", url, payload, authenticated=False, timeout=10)
        auth = data.get("auth") if isinstance(data, dict) else None
        token = auth.get("client_token") if isinstance(auth, dict) else None
        lease_duration = auth.get("lease_duration") if isinstance(auth, dict) else None
        if not token:
            raise KeyProviderError("Vault authentication response is missing required fields")
        try:
            lease_seconds = int(lease_duration)
        except (TypeError, ValueError) as exc:
            raise KeyProviderError("Vault authentication response is missing required fields") from exc
        if lease_seconds <= 0:
            raise KeyProviderError("Vault authentication response has an invalid lease")
        return str(token), time.monotonic() + lease_seconds

    def _get_token(self) -> str:
        """Get a valid token, refreshing if needed."""
        with self._token_lock:
            if self._token is None or self._token_expires_soon():
                self._token, self._token_expires_at = self._authenticate()
            return self._token

    def _token_expires_soon(self) -> bool:
        return time.monotonic() >= self._token_expires_at - self.token_renewal_margin_seconds

    def _clear_token(self) -> None:
        with self._token_lock:
            self._token = None
            self._token_expires_at = 0.0

    def _refresh_token(self) -> str:
        with self._token_lock:
            self._token, self._token_expires_at = self._authenticate()
            return self._token

    def _make_request(self, method: str, path: str, json_data: dict) -> dict:
        token = self._get_token()
        url = f"{self.vault_addr}/v1/{path}"
        return self._send(
            method,
            url,
            json_data,
            authenticated=True,
            token=token,
            timeout=15,
            retry_auth_once=True,
        )

    def _send(
        self,
        method: str,
        url: str,
        json_data: dict,
        *,
        authenticated: bool,
        token: Optional[str] = None,
        timeout: int,
        retry_auth_once: bool = False,
    ) -> dict:
        headers = {}
        if authenticated:
            if not token:
                raise KeyProviderError("Vault token is missing")
            headers["X-Vault-Token"] = token
        response = self._request(method, url, headers, json_data, timeout)
        if authenticated and retry_auth_once and response.status_code in {401, 403}:
            self._clear_token()
            headers["X-Vault-Token"] = self._refresh_token()
            response = self._request(method, url, headers, json_data, timeout)

        return self._handle_response(response)

    def _request(self, method: str, url: str, headers: dict, json_data: dict, timeout: int) -> requests.Response:
        try:
            return self.session.request(method, url, headers=headers, json=json_data, timeout=timeout)
        except (requests.Timeout, requests.ConnectionError, requests.exceptions.SSLError) as exc:
            raise InfrastructureUnavailableError("Vault is unavailable") from exc
        except requests.RequestException as exc:
            raise InfrastructureUnavailableError("Vault request failed") from exc

    def _handle_response(self, response: requests.Response) -> dict:
        status_code = response.status_code
        if status_code >= 400:
            try:
                error_data = self._safe_json(response)
            except KeyProviderError:
                error_data = {}

            if _response_mentions_sealed(error_data):
                raise InfrastructureUnavailableError("Vault is unavailable because it is sealed")
            if status_code in {401, 403}:
                raise KeyProviderError("Vault authentication or authorization failed")
            if status_code == 404:
                raise KeyProviderError("Vault path or key was not found")
            if status_code == 429:
                raise InfrastructureUnavailableError("Vault rate limit exceeded")
            if 500 <= status_code:
                raise InfrastructureUnavailableError("Vault service error")
            raise KeyProviderError("Vault request was rejected")

        data = self._safe_json(response)
        if _response_mentions_sealed(data):
            raise InfrastructureUnavailableError("Vault is unavailable because it is sealed")
        return data

    def _safe_json(self, response: requests.Response) -> dict:
        try:
            data = response.json()
        except ValueError as exc:
            raise KeyProviderError("Vault response was not valid JSON") from exc
        if not isinstance(data, dict):
            raise KeyProviderError("Vault response JSON was not an object")
        return data

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
        response_data = data.get("data") if isinstance(data, dict) else None
        ciphertext = response_data.get("ciphertext") if isinstance(response_data, dict) else None
        if not ciphertext:
            raise KeyProviderError("Vault encrypt response is missing required fields")
        return ciphertext.encode('ascii')

    @retry(
        stop=stop_after_attempt(3),
        wait=wait_exponential(multiplier=1, min=1, max=5),
        retry=retry_if_exception_type(InfrastructureUnavailableError),
        reraise=True,
    )
    def unwrap_dek(self, encrypted_dek: bytes) -> bytes:
        """Decrypt DEK using Vault transit."""
        try:
            ciphertext = encrypted_dek.decode('ascii')
        except UnicodeDecodeError as exc:
            raise KeyProviderError("Vault ciphertext is not valid ASCII") from exc
        if not ciphertext.startswith("vault:"):
            raise KeyProviderError("Vault ciphertext is malformed")
        path = f"transit/decrypt/{self.transit_key}"
        payload = {"ciphertext": ciphertext}
        data = self._make_request("POST", path, payload)
        response_data = data.get("data") if isinstance(data, dict) else None
        plaintext_b64 = response_data.get("plaintext") if isinstance(response_data, dict) else None
        if not plaintext_b64:
            raise KeyProviderError("Vault decrypt response is missing required fields")
        try:
            return base64.b64decode(plaintext_b64, validate=True)
        except (binascii.Error, ValueError) as exc:
            raise KeyProviderError("Vault decrypt response contained invalid base64") from exc
