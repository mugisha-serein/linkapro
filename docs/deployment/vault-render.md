# Vault On Render Deployment Notes

This note documents the required deployment order for introducing the single-node Render Vault service and the identity encryption migrations. It is intentionally operationally narrow: no secrets, tokens, DEKs, ciphertexts, Secret IDs, or Vault response bodies belong in this file or in deployment logs.

## Required Order

1. Deploy the Vault service definition and image/config artifacts first, without changing Django or Celery environment variables yet.
2. Attach the persistent disk at `/vault/data` and mount TLS material at the runtime-only paths referenced by `deploy/vault/config/vault.hcl`.
3. Start the private Vault service and manually initialize it if it is a new Vault data directory.
4. Manually unseal Vault after startup; this deployment does not configure auto-unseal and Vault remains sealed after restart until manually unsealed.
5. Run the one-time manual bootstrap script with `VAULT_ADDR` and a privileged bootstrap token supplied only through the operator environment. The script enables Transit, creates `linkapro-payments-kek` if absent, loads `linkapro-encryption`, creates/updates the `payments-app` AppRole, prints the Role ID, and shows the generated Secret ID once.
6. Store the AppRole Role ID and Secret ID in the deployment secret manager for Django web, Celery worker, and Celery beat, preferably through `VAULT_ROLE_ID_FILE` and `VAULT_SECRET_ID_FILE`; configure `VAULT_ADDR` as HTTPS and set `VAULT_TRANSIT_KEY_NAME=linkapro-payments-kek`.
7. From the same runtime environment that Django/Celery will use, run `python manage.py vault_preflight` and require it to pass before any encryption migration or app rollout.
8. Run Django migrations only after preflight passes. Migrations `0010_encrypt_oauth_tokens.py` and `0011_encrypt_totp_secret.py` call Vault only when plaintext OAuth tokens or TOTP secrets exist; they do not print plaintext token/secret values, generated DEKs, wrapped DEKs, ciphertexts, Vault tokens, Secret IDs, or response bodies.
9. Start or roll Django web, Celery worker, and Celery beat after migrations complete, then monitor application logs for sanitized Vault availability/configuration errors only.

## Migration Logging Check

`django_app/identity/migrations/0010_encrypt_oauth_tokens.py` contains no logging or print calls. It reads plaintext `access_token` and optional `refresh_token` only to encrypt them into the new encrypted fields before removing the plaintext columns.

`django_app/identity/migrations/0011_encrypt_totp_secret.py` contains no logging or print calls. It reads plaintext `totp_secret` only to encrypt it into the replacement encrypted JSON field before renaming that field back to `totp_secret`.

Both migrations rely on `VaultKeyProvider.wrap_dek()` for the wrapped DEK and fail the migration if Vault configuration/auth/connectivity is not ready. That is intentional: run `vault_preflight` before `migrate`.
