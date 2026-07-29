import secrets
from urllib.parse import urlparse

from django.conf import settings
from django.core.management.base import BaseCommand, CommandError

from payments.application.exceptions import InfrastructureUnavailableError, KeyProviderError
from payments.infrastructure.vault_key_provider import VaultKeyProvider


class Command(BaseCommand):
    help = "Run a sanitized Vault preflight check for field-encryption readiness."

    def handle(self, *args, **options):
        try:
            _VaultPreflight(self).run()
        except (InfrastructureUnavailableError, KeyProviderError, ValueError) as exc:
            raise CommandError(str(exc)) from exc


class _VaultPreflight:
    def __init__(self, command: BaseCommand):
        self.command = command
        self.provider = VaultKeyProvider()

    def run(self) -> None:
        self._check_address_configured()
        self._check_health_and_tls()
        self._check_approle_auth()
        self._check_transit_round_trip()
        self._ok("Vault preflight completed")

    def _check_address_configured(self) -> None:
        vault_addr = str(getattr(settings, "VAULT_ADDR", "") or "").strip()
        parsed = urlparse(vault_addr)
        if not vault_addr or parsed.scheme not in {"http", "https"} or not parsed.netloc:
            raise KeyProviderError("Vault address is not configured correctly")
        self._ok("address configured")

    def _check_health_and_tls(self) -> None:
        parsed = urlparse(self.provider.vault_addr)
        health_url = (
            f"{self.provider.vault_addr}/v1/sys/health"
            "?standbyok=true&perfstandbyok=true&sealedcode=200&uninitcode=200"
        )
        response = self.provider._request("GET", health_url, {}, {}, self.provider.request_timeout_seconds)
        data = self.provider._handle_response(response)
        if parsed.scheme == "https":
            self._ok("TLS trust")
        else:
            self._ok("TLS trust skipped for local/test HTTP Vault address")

        if data.get("initialized") is not True:
            raise InfrastructureUnavailableError("Vault is not initialized")
        self._ok("initialized")

        if data.get("sealed") is True:
            raise InfrastructureUnavailableError("Vault is sealed")
        if data.get("sealed") is not False:
            raise KeyProviderError("Vault health response is missing sealed status")
        self._ok("unsealed")

    def _check_approle_auth(self) -> None:
        self.provider._get_token()
        self._ok("AppRole auth")

    def _check_transit_round_trip(self) -> None:
        dek = secrets.token_bytes(32)
        ciphertext = self.provider.wrap_dek(dek)
        self._ok("Transit reachable")
        self._ok("Transit key exists and capabilities allow encrypt")

        decrypted = self.provider.unwrap_dek(ciphertext)
        self._ok("Transit key capabilities allow decrypt")
        if decrypted != dek:
            raise KeyProviderError("Vault encrypt/decrypt round-trip mismatch")
        self._ok("encrypt/decrypt round-trip")

    def _ok(self, label: str) -> None:
        self.command.stdout.write(self.command.style.SUCCESS(f"OK: {label}"))
