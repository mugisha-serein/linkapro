# Vault On Render Deployment

This document covers the LinkaPro Vault deployment path for field encryption on Render. It intentionally contains no real Vault tokens, AppRole Secret IDs, unseal keys, database values, DEKs, ciphertexts, OAuth tokens, or TOTP secrets.

## Why Vault Is Required

LinkaPro uses envelope encryption for sensitive application fields. The database stores encrypted field payloads plus a Vault-wrapped data encryption key (DEK). Vault Transit is the key-encryption-key boundary: application code can ask Vault to wrap or unwrap a 32-byte DEK, but the Transit key material never leaves Vault.

Vault is required for:

- Payment encrypted fields that already depend on `payments.infrastructure.crypto` and `VaultKeyProvider`.
- Identity OAuth token encryption in `interface/identity/migrations/0010_encrypt_oauth_tokens.py`.
- Identity TOTP secret encryption in `interface/identity/migrations/0011_encrypt_totp_secret.py`.
- Any future Django/Celery code path that reads or writes those encrypted fields.

If Vault is sealed, unreachable, misconfigured, or missing Transit permissions, encrypted-field reads/writes fail by design.

## Safer Hosting Recommendation

Managed HCP Vault is safer than a single self-hosted Render instance for this critical path. A managed Vault deployment can provide stronger availability, operational guardrails, managed upgrades, integrated storage durability, and safer recovery workflows. The Render setup in this repository is a single-node option, not a high-availability Vault architecture.

## Local Development

Local compose Vault is opt-in only:

```sh
docker compose --profile vault up vault
```

The compose service is local-only and dev-mode only:

- It uses `hashicorp/vault:1.18.4`.
- It is behind the `vault` profile and never starts by default.
- It binds the host port to `127.0.0.1:8200`.
- It uses a non-production dev token.
- It has no durable Vault data volume; data is lost when the dev Vault container is removed or restarted.

Host tools can use `VAULT_ADDR=http://127.0.0.1:8200`. Django and Celery containers use `COMPOSE_VAULT_ADDR=http://vault:8200` by default so they can reach the compose service by DNS name. HTTP Vault addresses are acceptable only for local/test settings.

## Render Private Service

`render-vault.yaml` defines a private Render service:

- `type: pserv`
- Docker runtime using `deploy/vault/Dockerfile`
- Region `frankfurt`
- One instance
- Persistent disk mounted at `/vault/data`
- No public URL

The blueprint comments are intentional: this is not highly available, and Vault stays sealed after restart until manually unsealed. Do not add pretend auto-unseal unless a real KMS-backed auto-unseal design is implemented and tested.

## TLS Handling

Production Vault must use HTTPS. `deploy/vault/config/vault.hcl` configures a TCP listener on `0.0.0.0:8200` with TLS enabled and runtime-only file paths:

- `/vault/tls/tls.crt`
- `/vault/tls/tls.key`
- `/vault/tls/ca.crt`

Do not commit certificate private keys or CA material. Mount them through the deployment environment. Django/Celery can set `VAULT_CACERT` to the mounted CA bundle path when the Vault certificate chain is not trusted by the container base image.

Production settings reject HTTP `VAULT_ADDR` values. Development and test settings allow local HTTP for local-only Vault.

## Init And Unseal

For a new `/vault/data` directory, initialize Vault manually. Store unseal material outside the repo in an approved secrets/recovery system. Never paste unseal keys into source files, docs, CI logs, issue comments, or chat transcripts.

After every Vault service restart, manually unseal the single-node Render Vault before starting or rolling Django/Celery workloads that need encrypted fields. If Vault remains sealed, `vault_preflight` and encrypted-field operations fail.

## Transit, AppRole, And Policy Setup

Run `deploy/vault/scripts/bootstrap.sh` manually after Vault is initialized and unsealed. It requires `VAULT_ADDR` and a privileged bootstrap token in the operator environment. The script does not write credentials to repo files.

The bootstrap script is idempotent for the expected setup:

- Enables the Transit secrets engine at `transit/` if needed.
- Creates `linkapro-payments-kek` if needed.
- Enables AppRole auth if needed.
- Writes the `linkapro-encryption` policy.
- Creates or updates the `payments-app` AppRole.
- Prints the Role ID.
- Generates a Secret ID and shows it once so it can be stored in the deployment secret manager.

The committed policy grants only:

- `update` on `transit/encrypt/linkapro-payments-kek`
- `update` on `transit/decrypt/linkapro-payments-kek`

There are no root, wildcard, admin, or rewrap capabilities in the application policy.

## Environment Variables

Django web, Celery worker, and Celery beat need the same Vault configuration:

- `VAULT_ADDR`: HTTPS production Vault address.
- `VAULT_ROLE_ID` or `VAULT_ROLE_ID_FILE`: AppRole Role ID, with file-based value preferred.
- `VAULT_SECRET_ID` or `VAULT_SECRET_ID_FILE`: AppRole Secret ID, with file-based value preferred.
- `VAULT_TRANSIT_KEY_NAME`: `linkapro-payments-kek`.
- `VAULT_NAMESPACE`: optional, only when using Vault Enterprise namespaces.
- `VAULT_CACERT`: optional CA bundle path for TLS verification.
- `VAULT_AUTH_TIMEOUT_SECONDS`: positive integer.
- `VAULT_REQUEST_TIMEOUT_SECONDS`: positive integer.
- `VAULT_TOKEN_RENEWAL_MARGIN_SECONDS`: non-negative integer.

File-based credential variables take precedence over direct values. Credential files must be readable and non-blank. Do not log Role IDs, Secret IDs, Vault tokens, DEKs, ciphertext values, OAuth tokens, or TOTP secrets.

## Django And Celery Configuration

`docker-compose.yml` passes the shared Vault environment block to:

- `django`
- `celery_worker`
- `celery_beat`

Production deploys must do the same in Render service configuration. Django settings validate Vault configuration during settings import, but they do not authenticate to Vault or make network calls at import time.

Run `python manage.py vault_preflight` from the same runtime image/environment used by Django and Celery before migrations or rollout.

## Preflight

`python manage.py vault_preflight` checks:

- Vault address is configured.
- TLS trust path is usable for HTTPS, or local/test HTTP is explicitly detected.
- Vault is initialized.
- Vault is unsealed.
- AppRole authentication succeeds.
- Transit encrypt/decrypt is reachable.
- The configured key exists and policy allows encrypt/decrypt.
- A temporary 32-byte DEK wraps and unwraps to the same value.

The command must not print DEKs, ciphertext, Vault tokens, Secret IDs, or raw Vault response bodies. Treat any preflight failure as a deployment blocker.

## Required Migration Order

Use this order for the Vault rollout and identity encryption migrations:

1. Deploy the Vault service definition and image/config artifacts first, without changing Django or Celery environment variables yet.
2. Attach the persistent disk at `/vault/data` and mount TLS material at the runtime-only paths referenced by `deploy/vault/config/vault.hcl`.
3. Start the private Vault service and manually initialize it if it is a new Vault data directory.
4. Manually unseal Vault after startup; this deployment does not configure auto-unseal and Vault remains sealed after restart until manually unsealed.
5. Run the one-time manual bootstrap script with `VAULT_ADDR` and a privileged bootstrap token supplied only through the operator environment.
6. Store the AppRole Role ID and Secret ID in the deployment secret manager for Django web, Celery worker, and Celery beat, preferably through `VAULT_ROLE_ID_FILE` and `VAULT_SECRET_ID_FILE`; configure HTTPS `VAULT_ADDR` and `VAULT_TRANSIT_KEY_NAME=linkapro-payments-kek`.
7. From the same runtime environment that Django/Celery will use, run `python manage.py vault_preflight` and require it to pass before any encryption migration or app rollout.
8. Run Django migrations only after preflight passes. Migrations `0010_encrypt_oauth_tokens.py` and `0011_encrypt_totp_secret.py` call Vault only when plaintext OAuth tokens or TOTP secrets exist; they do not print plaintext token/secret values, generated DEKs, wrapped DEKs, ciphertexts, Vault tokens, Secret IDs, or response bodies.
9. Start or roll Django web, Celery worker, and Celery beat after migrations complete, then monitor application logs for sanitized Vault availability/configuration errors only.

## Migration Logging Check

`interface/identity/migrations/0010_encrypt_oauth_tokens.py` contains no logging or print calls. It reads plaintext `access_token` and optional `refresh_token` only to encrypt them into the new encrypted fields before removing the plaintext columns.

`interface/identity/migrations/0011_encrypt_totp_secret.py` contains no logging or print calls. It reads plaintext `totp_secret` only to encrypt it into the replacement encrypted JSON field before renaming that field back to `totp_secret`.

Both migrations rely on `VaultKeyProvider.wrap_dek()` for the wrapped DEK and fail the migration if Vault configuration/auth/connectivity is not ready. That is intentional: run `vault_preflight` before `migrate`.

## Rotation

Rotate AppRole Secret IDs on a regular schedule and immediately after suspected exposure. Generate a new Secret ID, store it in the deployment secret manager, roll Django/Celery, confirm `vault_preflight`, then revoke the old Secret ID/accessor if available.

Rotate direct/file-mounted credential delivery without changing source files. Prefer file-mounted secrets so values are not exposed through process environment inspection.

Transit key rotation changes the active key version for new wraps, while existing Vault ciphertexts remain decryptable by Vault as long as old key versions are retained. The application policy currently does not grant `rewrap`; do not add it unless a specific, tested key-rotation workflow needs it.

Before disabling or deleting any Transit key version, prove that no stored `dek_encrypted` value depends on that version. Deleting required key versions can permanently make encrypted database fields unreadable.

## Raft Backup And Restore

The Render service uses integrated Raft storage at `/vault/data`. Back up Vault state before upgrades, migrations, key policy changes, and any storage maintenance. Keep backups encrypted and access-controlled outside the repo.

Restore must be rehearsed in a non-production environment. A useful restore drill proves:

- Vault starts from restored Raft data.
- Required unseal material works.
- Transit key `linkapro-payments-kek` exists.
- The `payments-app` AppRole/policy can authenticate and decrypt test data.
- `python manage.py vault_preflight` passes from the Django runtime.

Do not rely on database backups alone. The database contains Vault-wrapped DEKs; without the matching Vault Transit key history, encrypted fields may be unrecoverable.

## DR And Availability Limits

This Render design is single-node Vault. It has important limits:

- No high availability.
- No automatic failover.
- No fake auto-unseal.
- Restart requires manual unseal.
- Persistent disk failure can be catastrophic without a valid Vault backup.
- Vault downtime blocks encrypted-field reads/writes in Django and Celery.

For production-critical use, prefer managed HCP Vault or a real highly available Vault cluster with tested auto-unseal, backups, restore drills, monitoring, and incident procedures.

## Troubleshooting

`VAULT_ADDR must be a valid HTTPS URL`: production is configured with HTTP, a malformed URL, or a URL containing unsupported params/query/fragment.

`VAULT_ROLE_ID_FILE could not be read` or `VAULT_SECRET_ID_FILE could not be read`: the file mount path is wrong, permissions are wrong, or the secret manager did not mount the file.

`must not be blank`: a credential file exists but contains only whitespace.

`Vault is unavailable because it is sealed`: manually unseal Vault and rerun `vault_preflight`.

`Vault authentication or authorization failed`: check AppRole Role ID/Secret ID freshness, policy attachment, token TTL, and whether the Secret ID has already been consumed.

`Vault path or key was not found`: confirm Transit is enabled at `transit/` and the key name matches `VAULT_TRANSIT_KEY_NAME`.

`Vault rate limit exceeded` or `Vault service error`: treat as transient infrastructure failure; retry after Vault recovers and check provider/service health.

`Vault response was not valid JSON` or `missing required fields`: check that traffic is reaching Vault, not a proxy/error page, and that the Vault API path is correct.

`Vault decrypt response DEK must be exactly 32 bytes`: stop and investigate data/key compatibility before changing database representation.
