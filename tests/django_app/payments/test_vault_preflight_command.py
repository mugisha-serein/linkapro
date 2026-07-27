from io import StringIO

import pytest
from django.core.management import call_command
from django.core.management.base import CommandError
from django.test import override_settings

from payments.application.exceptions import InfrastructureUnavailableError


class _Response:
    def __init__(self, payload):
        self.status_code = 200
        self._payload = payload

    def json(self):
        return self._payload


class _Provider:
    vault_addr = "https://vault.internal:8200"
    request_timeout_seconds = 15

    def __init__(self, *, sealed=False, initialized=True, mismatch=False):
        self.sealed = sealed
        self.initialized = initialized
        self.mismatch = mismatch
        self.last_dek = None

    def _request(self, method, url, headers, json_data, timeout):
        return _Response({"initialized": self.initialized, "sealed": self.sealed})

    def _handle_response(self, response):
        return response.json()

    def _get_token(self):
        return "vault-token-secret"

    def wrap_dek(self, dek):
        self.last_dek = dek
        return b"vault:v1:ciphertext-secret"

    def unwrap_dek(self, ciphertext):
        if self.mismatch:
            return b"x" * 32
        return self.last_dek


@override_settings(VAULT_ADDR="https://vault.internal:8200")
def test_vault_preflight_success_is_sanitized(monkeypatch):
    from django_app.payments.management.commands import vault_preflight

    monkeypatch.setattr(vault_preflight, "VaultKeyProvider", lambda: _Provider())
    stdout = StringIO()

    call_command("vault_preflight", stdout=stdout)

    output = stdout.getvalue()
    assert "OK: address configured" in output
    assert "OK: TLS trust" in output
    assert "OK: AppRole auth" in output
    assert "OK: encrypt/decrypt round-trip" in output
    assert "vault-token-secret" not in output
    assert "ciphertext-secret" not in output


@override_settings(VAULT_ADDR="http://127.0.0.1:8200")
def test_vault_preflight_allows_local_http(monkeypatch):
    from django_app.payments.management.commands import vault_preflight

    provider = _Provider()
    provider.vault_addr = "http://127.0.0.1:8200"
    monkeypatch.setattr(vault_preflight, "VaultKeyProvider", lambda: provider)
    stdout = StringIO()

    call_command("vault_preflight", stdout=stdout)

    assert "OK: TLS trust skipped for local/test HTTP Vault address" in stdout.getvalue()


@override_settings(VAULT_ADDR="")
def test_vault_preflight_fails_when_address_missing(monkeypatch):
    from django_app.payments.management.commands import vault_preflight

    monkeypatch.setattr(vault_preflight, "VaultKeyProvider", lambda: _Provider())

    with pytest.raises(CommandError, match="Vault address is not configured correctly"):
        call_command("vault_preflight", stdout=StringIO())


@override_settings(VAULT_ADDR="https://vault.internal:8200")
def test_vault_preflight_fails_when_sealed(monkeypatch):
    from django_app.payments.management.commands import vault_preflight

    monkeypatch.setattr(vault_preflight, "VaultKeyProvider", lambda: _Provider(sealed=True))

    with pytest.raises(CommandError, match="Vault is sealed"):
        call_command("vault_preflight", stdout=StringIO())


@override_settings(VAULT_ADDR="https://vault.internal:8200")
def test_vault_preflight_fails_when_round_trip_mismatches(monkeypatch):
    from django_app.payments.management.commands import vault_preflight

    monkeypatch.setattr(vault_preflight, "VaultKeyProvider", lambda: _Provider(mismatch=True))

    with pytest.raises(CommandError, match="round-trip mismatch"):
        call_command("vault_preflight", stdout=StringIO())


@override_settings(VAULT_ADDR="https://vault.internal:8200")
def test_vault_preflight_does_not_print_response_body(monkeypatch):
    from django_app.payments.management.commands import vault_preflight

    class _FailingProvider(_Provider):
        def _request(self, method, url, headers, json_data, timeout):
            raise InfrastructureUnavailableError("Vault is unavailable")

    monkeypatch.setattr(vault_preflight, "VaultKeyProvider", lambda: _FailingProvider())
    stdout = StringIO()

    with pytest.raises(CommandError, match="Vault is unavailable"):
        call_command("vault_preflight", stdout=stdout)

    assert "response" not in stdout.getvalue().lower()
