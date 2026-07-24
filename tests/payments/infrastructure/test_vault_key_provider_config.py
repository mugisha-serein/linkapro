import base64

import pytest
import requests
from django.test import override_settings

from payments.application.exceptions import InfrastructureUnavailableError, KeyProviderError
from payments.infrastructure.vault_key_provider import VaultKeyProvider


class _Response:
    def __init__(self, status_code=200, payload=None, json_error=None):
        self.status_code = status_code
        self._payload = payload if payload is not None else {"data": {}}
        self._json_error = json_error

    def json(self):
        if self._json_error:
            raise self._json_error
        return self._payload


@override_settings(
    VAULT_ADDR=" https://vault.internal:8200/ ",
    VAULT_ROLE_ID=" role-from-settings ",
    VAULT_SECRET_ID=" secret-from-settings ",
    VAULT_TRANSIT_KEY_NAME=" linkapro-payments-kek ",
    VAULT_NAMESPACE=" admin/linkapro ",
)
def test_vault_key_provider_strips_direct_config_values(monkeypatch):
    monkeypatch.delenv("VAULT_ROLE_ID_FILE", raising=False)
    monkeypatch.delenv("VAULT_SECRET_ID_FILE", raising=False)

    provider = VaultKeyProvider()

    assert provider.vault_addr == "https://vault.internal:8200"
    assert provider.role_id == "role-from-settings"
    assert provider.secret_id == "secret-from-settings"
    assert provider.transit_key == "linkapro-payments-kek"
    assert provider.namespace == "admin/linkapro"
    assert provider.session.headers["Accept"] == "application/json"
    assert provider.session.headers["Content-Type"] == "application/json"
    assert provider.session.headers["X-Vault-Namespace"] == "admin/linkapro"


@override_settings(
    VAULT_ADDR="https://vault.internal:8200",
    VAULT_ROLE_ID="direct-role",
    VAULT_SECRET_ID="direct-secret",
    VAULT_TRANSIT_KEY_NAME="linkapro-payments-kek",
)
def test_vault_key_provider_prefers_file_credentials(monkeypatch, tmp_path):
    role_file = tmp_path / "role-id"
    secret_file = tmp_path / "secret-id"
    role_file.write_text(" role-from-file \n", encoding="utf-8")
    secret_file.write_text("\nsecret-from-file\n", encoding="utf-8")
    monkeypatch.setenv("VAULT_ROLE_ID_FILE", str(role_file))
    monkeypatch.setenv("VAULT_SECRET_ID_FILE", str(secret_file))

    provider = VaultKeyProvider()

    assert provider.role_id == "role-from-file"
    assert provider.secret_id == "secret-from-file"


@override_settings(
    VAULT_ADDR="https://vault.internal:8200",
    VAULT_ROLE_ID="role-id",
    VAULT_SECRET_ID="secret-id",
    VAULT_TRANSIT_KEY_NAME="linkapro-payments-kek",
    VAULT_NAMESPACE="",
)
def test_vault_key_provider_sends_token_header_only_for_authenticated_requests(monkeypatch):
    provider = VaultKeyProvider()
    calls = []

    def request(method, url, headers=None, json=None, timeout=None):
        calls.append({"method": method, "url": url, "headers": headers or {}, "json": json, "timeout": timeout})
        if url.endswith("/auth/approle/login"):
            return _Response(payload={"auth": {"client_token": "vault-token"}})
        return _Response(payload={"data": {"ciphertext": "vault:v1:ciphertext"}})

    monkeypatch.setattr(provider.session, "request", request)

    assert provider.wrap_dek(b"0" * 32) == b"vault:v1:ciphertext"

    assert "X-Vault-Token" not in calls[0]["headers"]
    assert calls[1]["headers"]["X-Vault-Token"] == "vault-token"


@pytest.mark.parametrize(
    ("exc", "expected"),
    [
        (requests.ConnectionError("connection leaked detail"), InfrastructureUnavailableError),
        (requests.Timeout("timeout leaked detail"), InfrastructureUnavailableError),
        (requests.exceptions.SSLError("tls leaked detail"), InfrastructureUnavailableError),
    ],
)
@override_settings(
    VAULT_ADDR="https://vault.internal:8200",
    VAULT_ROLE_ID="role-id",
    VAULT_SECRET_ID="secret-id",
    VAULT_TRANSIT_KEY_NAME="linkapro-payments-kek",
)
def test_vault_key_provider_maps_transport_failures_without_raw_detail(monkeypatch, exc, expected):
    provider = VaultKeyProvider()
    monkeypatch.setattr(provider.session, "request", lambda *args, **kwargs: (_ for _ in ()).throw(exc))

    with pytest.raises(expected) as raised:
        provider.wrap_dek(b"0" * 32)

    assert "leaked detail" not in str(raised.value)


@pytest.mark.parametrize(
    ("status_code", "payload", "expected"),
    [
        (401, {"errors": ["permission body"]}, KeyProviderError),
        (403, {"errors": ["permission body"]}, KeyProviderError),
        (404, {"errors": ["missing body"]}, KeyProviderError),
        (429, {"errors": ["rate body"]}, InfrastructureUnavailableError),
        (500, {"errors": ["server body"]}, InfrastructureUnavailableError),
        (503, {"errors": ["Vault is sealed"]}, InfrastructureUnavailableError),
    ],
)
@override_settings(
    VAULT_ADDR="https://vault.internal:8200",
    VAULT_ROLE_ID="role-id",
    VAULT_SECRET_ID="secret-id",
    VAULT_TRANSIT_KEY_NAME="linkapro-payments-kek",
)
def test_vault_key_provider_maps_http_failures_without_raw_body(monkeypatch, status_code, payload, expected):
    provider = VaultKeyProvider()
    monkeypatch.setattr(provider.session, "request", lambda *args, **kwargs: _Response(status_code, payload))

    with pytest.raises(expected) as raised:
        provider.wrap_dek(b"0" * 32)

    assert "body" not in str(raised.value)
    assert "Vault is sealed" not in str(raised.value)


@pytest.mark.parametrize(
    ("response", "expected_message"),
    [
        (_Response(payload={"auth": {}}, status_code=200), "missing required fields"),
        (_Response(payload={"data": {}}, status_code=200), "missing required fields"),
        (_Response(json_error=ValueError("raw json body"), status_code=200), "not valid JSON"),
    ],
)
@override_settings(
    VAULT_ADDR="https://vault.internal:8200",
    VAULT_ROLE_ID="role-id",
    VAULT_SECRET_ID="secret-id",
    VAULT_TRANSIT_KEY_NAME="linkapro-payments-kek",
)
def test_vault_key_provider_maps_invalid_response_shapes(monkeypatch, response, expected_message):
    provider = VaultKeyProvider()
    monkeypatch.setattr(provider.session, "request", lambda *args, **kwargs: response)

    with pytest.raises(KeyProviderError) as raised:
        provider.wrap_dek(b"0" * 32)

    assert expected_message in str(raised.value)
    assert "raw json body" not in str(raised.value)


@override_settings(
    VAULT_ADDR="https://vault.internal:8200",
    VAULT_ROLE_ID="role-id",
    VAULT_SECRET_ID="secret-id",
    VAULT_TRANSIT_KEY_NAME="linkapro-payments-kek",
)
def test_vault_key_provider_maps_invalid_base64(monkeypatch):
    provider = VaultKeyProvider()
    provider._token = "vault-token"
    monkeypatch.setattr(
        provider.session,
        "request",
        lambda *args, **kwargs: _Response(payload={"data": {"plaintext": "not-base64!"}}),
    )

    with pytest.raises(KeyProviderError, match="invalid base64"):
        provider.unwrap_dek(b"vault:v1:ciphertext")


@override_settings(
    VAULT_ADDR="https://vault.internal:8200",
    VAULT_ROLE_ID="role-id",
    VAULT_SECRET_ID="secret-id",
    VAULT_TRANSIT_KEY_NAME="linkapro-payments-kek",
)
def test_vault_key_provider_rejects_malformed_ciphertext_before_request(monkeypatch):
    provider = VaultKeyProvider()
    provider._token = "vault-token"
    request = lambda *args, **kwargs: _Response(payload={"data": {"plaintext": base64.b64encode(b"0" * 32).decode()}})
    monkeypatch.setattr(provider.session, "request", request)

    with pytest.raises(KeyProviderError, match="malformed"):
        provider.unwrap_dek(b"not-a-vault-ciphertext")
