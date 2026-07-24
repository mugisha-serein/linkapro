from django.test import override_settings

from payments.infrastructure.vault_key_provider import VaultKeyProvider


@override_settings(
    VAULT_ADDR=" https://vault.internal:8200/ ",
    VAULT_ROLE_ID=" role-from-settings ",
    VAULT_SECRET_ID=" secret-from-settings ",
    VAULT_TRANSIT_KEY_NAME=" linkapro-payments-kek ",
)
def test_vault_key_provider_strips_direct_config_values(monkeypatch):
    monkeypatch.delenv("VAULT_ROLE_ID_FILE", raising=False)
    monkeypatch.delenv("VAULT_SECRET_ID_FILE", raising=False)

    provider = VaultKeyProvider()

    assert provider.vault_addr == "https://vault.internal:8200"
    assert provider.role_id == "role-from-settings"
    assert provider.secret_id == "secret-from-settings"
    assert provider.transit_key == "linkapro-payments-kek"


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
