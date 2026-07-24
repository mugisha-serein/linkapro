# Vault Dependency Map

This map documents every current place the Django/Celery code reads Vault configuration, calls Vault, or assumes Vault-backed envelope encryption exists. It is an audit note only; it does not prescribe or change behavior.

## Runtime Contract

The application uses HashiCorp Vault Transit as the key-encryption-key service for envelope encryption. Application code generates a per-record data encryption key (DEK), encrypts sensitive field data locally with AES-256-GCM, then asks Vault to wrap or unwrap that DEK through the Transit engine.

The central port is `payments.application.ports.IKeyProvider`. It exposes only `wrap_dek(dek: bytes) -> bytes` and `unwrap_dek(encrypted_dek: bytes) -> bytes`. Although it lives under payments, identity now reuses this port and the payments crypto helpers for OAuth tokens and TOTP secrets.

## Direct Vault Client

`payments/infrastructure/vault_key_provider.py`

- Reads `settings.VAULT_ADDR`, `settings.VAULT_ROLE_ID`, `settings.VAULT_SECRET_ID`, and `settings.VAULT_TRANSIT_KEY_NAME` at construction time.
- Assumes `settings.VAULT_ADDR` is a string because it calls `.rstrip("/")` immediately.
- Authenticates with AppRole via `POST {VAULT_ADDR}/v1/auth/approle/login`.
- Sends `role_id` and `secret_id` in the AppRole login JSON payload.
- Caches the returned Vault token in memory on the provider instance.
- Calls Transit encrypt at `transit/encrypt/{VAULT_TRANSIT_KEY_NAME}` to wrap DEKs.
- Calls Transit decrypt at `transit/decrypt/{VAULT_TRANSIT_KEY_NAME}` to unwrap DEKs.
- Retries `wrap_dek` and `unwrap_dek` up to 3 attempts on `InfrastructureUnavailableError` with exponential backoff.
- On HTTP 403 from a Transit request, clears the cached token, re-authenticates once, and retries that request.
- Converts Vault request/auth failures into `InfrastructureUnavailableError`.

## Payment Construction

`payments/infrastructure/factories.py`

- `build_payment_key_provider()` constructs `VaultKeyProvider()`.
- `build_payment_command_handlers()` constructs one key provider and passes it to:
  - `DjangoPaymentRepository`
  - `DjangoWebhookEventRepository`
  - `DjangoAuditLogger`
  - `DjangoExpiryScanner`
- `build_payment_query_handlers()` constructs a key provider for `DjangoPaymentRepository`.
- `build_payment_expiry_scanner()` defaults to a new Vault-backed provider when one is not injected.

## Shared Crypto

`payments/infrastructure/crypto.py`

- Does not call Vault or read settings.
- Encrypts/decrypts bytes using AES-256-GCM and a caller-supplied plaintext DEK.
- Returns `EncryptedField` with `dek_encrypted=b""`; repositories fill the wrapped DEK after calling the key provider.

`payments/helpers/encryption.py`

- Serializes/deserializes `EncryptedField` values to JSON-safe dictionaries.
- Does not call Vault, but its JSON shape is assumed by all Vault-backed fields.

## Payment Persistence

`payments/infrastructure/repositories.py`

- `DjangoPaymentRepository.__init__` requires a non-null `IKeyProvider`.
- `DjangoPaymentRepository.save()`:
  - Generates a 32-byte DEK.
  - Calls `key_provider.wrap_dek(dek)`.
  - Encrypts `payment.metadata` locally with AES-GCM.
  - Stores encrypted metadata JSON and also stores `dek_encrypted` on the payment row.
- `DjangoPaymentRepository._to_domain()`:
  - Calls `_decrypt_json_field(model.metadata, model.dek_encrypted)`.
  - When metadata has encrypted-field keys and `model.dek_encrypted` exists, calls `key_provider.unwrap_dek(wrapped_dek)`.
  - Uses the unwrapped DEK to decrypt metadata.
  - Leaves legacy/plain dict metadata untouched if it is not in encrypted-field shape.
- `DjangoWebhookEventRepository.__init__` requires a non-null `IKeyProvider`.
- `DjangoWebhookEventRepository.save_event()`:
  - Generates a 32-byte DEK.
  - Calls `key_provider.wrap_dek(dek)`.
  - Encrypts the webhook payload locally.
  - Stores encrypted payload JSON and `dek_encrypted` on the webhook event row.
- `DjangoApiKeyRepository` does not use Vault; API key storage still reads `secret_plain`.

`payments/infrastructure/audit_logger.py`

- `DjangoAuditLogger` receives an `IKeyProvider`.
- `log()` generates a 32-byte DEK, calls `key_provider.wrap_dek(dek)`, encrypts audit event details locally, and stores encrypted details plus `dek_encrypted` on `AuditLog`.

`payments/infrastructure/expiry_scanner.py`

- `DjangoExpiryScanner` requires an `IKeyProvider`.
- It constructs `DjangoPaymentRepository(key_provider)` and returns expired payments through `payment_repo._to_domain`, so expired-payment scanning can unwrap payment metadata DEKs.

`payments/tasks.py`

- `_decrypt_retry_payload()` calls `build_payment_key_provider()` when a provider is not supplied.
- It unwraps `WebhookEvent.dek_encrypted` before decrypting retry payload JSON.
- `_load_retry_event()` always builds a payment key provider before scanning retryable/terminal webhook events.
- `expire_stale_payments_task()` calls `build_payment_command_handlers()`, which creates a Vault-backed provider through factories.

## Identity Reuse

`infrastructure/repos/django_user_repository.py`

- Imports `VaultKeyProvider` from payments infrastructure.
- `DjangoUserRepository.__init__` defaults to `VaultKeyProvider()` when no key provider is injected.
- Normal user save/load paths do not encrypt/decrypt with Vault.
- `set_totp_secret()`:
  - Generates a 32-byte DEK.
  - Calls `key_provider.wrap_dek(dek)`.
  - Encrypts the TOTP secret locally with AES-GCM.
  - Stores encrypted JSON in `User.totp_secret`.
- `get_totp_secret()`:
  - Reads encrypted JSON from `User.totp_secret`.
  - Calls `key_provider.unwrap_dek(encrypted.dek_encrypted)`.
  - Decrypts locally and returns a `TOTPSecret` value object.
- `clear_totp_secret()` does not call Vault; it clears the stored encrypted value.

`infrastructure/repos/django_oauth_token_repository.py`

- Imports `VaultKeyProvider` from payments infrastructure.
- `DjangoOAuthTokenRepository.__init__` defaults to `VaultKeyProvider()` when no key provider is injected.
- `save()`:
  - Generates a 32-byte DEK.
  - Calls `key_provider.wrap_dek(dek)`.
  - Encrypts OAuth access and refresh tokens locally.
  - Stores encrypted token JSON and `dek_encrypted` on the OAuth token row.
- `_to_domain()`:
  - Calls `_decrypt_token()` for the access token and optionally the refresh token.
  - `_decrypt_token()` calls `key_provider.unwrap_dek(wrapped_dek)` and decrypts locally.

## Identity Data Migrations

`django_app/identity/migrations/0010_encrypt_oauth_tokens.py`

- Adds `encrypted_access_token`, `encrypted_refresh_token`, and `dek_encrypted`.
- If any row has `encrypted_access_token__isnull=True`, imports and constructs `VaultKeyProvider`.
- For every plaintext OAuth token row:
  - Generates a DEK.
  - Calls `key_provider.wrap_dek(dek)`.
  - Encrypts plaintext `access_token` and optional `refresh_token`.
  - Saves encrypted fields and `dek_encrypted`.
- Removes old plaintext `access_token` and `refresh_token` columns.
- If there are no plaintext rows to migrate, it returns before constructing Vault.

`django_app/identity/migrations/0011_encrypt_totp_secret.py`

- Adds temporary `encrypted_totp_secret`.
- If any user has a non-null, non-empty `totp_secret`, imports and constructs `VaultKeyProvider`.
- For every plaintext TOTP row:
  - Generates a DEK.
  - Calls `key_provider.wrap_dek(dek)`.
  - Encrypts plaintext `totp_secret`.
  - Saves encrypted JSON into `encrypted_totp_secret`.
- Removes old `totp_secret` and renames `encrypted_totp_secret` back to `totp_secret`.
- If no plaintext TOTP secrets exist, it returns before constructing Vault.

## Settings

`django_app/settings/base.py`

- Reads:
  - `VAULT_ADDR = os.environ.get("VAULT_ADDR")`
  - `VAULT_ROLE_ID = os.environ.get("VAULT_ROLE_ID", "")`
  - `VAULT_SECRET_ID = os.environ.get("VAULT_SECRET_ID", "")`
  - `VAULT_TRANSIT_KEY_NAME = os.environ.get("VAULT_TRANSIT_KEY_NAME", "linkapro-payments-kek")`
- Does not validate that Vault settings are present.
- Because `VAULT_ADDR` defaults to `None`, constructing `VaultKeyProvider` without an env value will fail before any network call.

`django_app/settings/production.py`

- Fails at import time if any of `VAULT_ADDR`, `VAULT_ROLE_ID`, `VAULT_SECRET_ID`, or `VAULT_TRANSIT_KEY_NAME` is blank.
- Error text states they are required for production field encryption.
- This protects Django web and Celery processes configured with production settings from starting without Vault config.

`django_app/settings/test.py`

- Defaults `VAULT_ADDR` to `http://localhost:8200`.
- Defaults `VAULT_TRANSIT_KEY_NAME` to `linkapro-payments-kek`.
- Leaves `VAULT_ROLE_ID` and `VAULT_SECRET_ID` blank unless supplied.
- Tests that touch encrypted fields generally inject fake key providers, so the test settings do not imply a live Vault service.

## Containers And Environment

`docker-compose.yml`

- Passes `VAULT_ADDR`, `VAULT_ROLE_ID`, `VAULT_SECRET_ID`, and `VAULT_TRANSIT_KEY_NAME` into:
  - `django`
  - `celery_worker`
  - `celery_beat`
- Does not pass Vault settings into `fastapi`.
- The Django container runs migrations before starting Gunicorn, so identity migrations that need to encrypt existing plaintext rows may call Vault during container startup.
- Celery worker tasks can call Vault through payment factories and identity repositories.
- Celery beat receives Vault env even though its direct role is scheduling; this keeps settings import consistent under production fail-fast validation.

`Dockerfile.django`

- Does not read Vault env or install Vault CLI.
- Installs Python dependencies and runs the Django app as the `django` user.
- Runtime Vault access is through Python `requests`, not a system Vault binary.

`.env.example`

- Documents required local/prod Vault variables:
  - `VAULT_ADDR`
  - `VAULT_ROLE_ID`
  - `VAULT_SECRET_ID`
  - `VAULT_TRANSIT_KEY_NAME`
- Uses placeholder values, including `your-payment-trans-it-key-name`.
- Also documents `PROVIDER_REFERENCE_HMAC_KEY`, which is separate from Vault but adjacent to payment secret handling.

`scripts/vault-dev-setup.ps1`

- Sets local shell `VAULT_ADDR` to `http://127.0.0.1:8200`.
- Enables the Transit secrets engine.
- Creates the Transit key `linkapro-payments-kek`.
- Enables AppRole auth.
- Writes a `payments-policy` policy from `payments-policy.hcl`.
- Creates AppRole `payments-app` with `payments-policy`, `token_ttl=1h`, and `token_max_ttl=4h`.
- Prints/creates the role ID and secret ID needed for app env variables.

## Test Coverage And Assumptions

`tests/django_app/identity/test_email_settings.py`

- Production settings tests include Vault env in the happy-path environment.
- `test_production_settings_raise_if_vault_addr_missing` verifies production import fails when `VAULT_ADDR` is absent.
- The suite does not currently test missing `VAULT_ROLE_ID`, `VAULT_SECRET_ID`, or `VAULT_TRANSIT_KEY_NAME` individually, but production settings check the same list.

`tests/payments/infrastructure/test_encryption.py`

- Tests AES-GCM encrypt/decrypt and encrypted-field JSON round trips.
- Treats the wrapped DEK as simulated Vault output (`b"fake_wrapped_dek"`).
- Does not call `VaultKeyProvider`.

`tests/payments/infrastructure/test_payment_repository_contract.py`

- Injects a `MagicMock` key provider.
- Verifies `DjangoPaymentRepository.save()` calls `wrap_dek`.
- Verifies encrypted metadata stores `dek_encrypted` and can be read back through the fake unwrap path.

`tests/payments/tasks/test_webhook_retry_task.py`

- Builds a fake key provider that maps wrapped DEKs back to plaintext DEKs.
- Patches `payments.tasks.build_payment_key_provider` so retry payload decryption does not call live Vault.
- Verifies encrypted webhook payload retry behavior.

`tests/payments/application/test_transaction_boundaries.py`

- Injects fake key providers into payment repository, webhook repository, and audit logger.
- Covers transaction ordering around encrypted webhook/audit writes without live Vault.

`tests/payments/integration/test_webhook_pipeline.py`

- Uses a mock key provider to exercise webhook pipeline encryption/decryption behavior without live Vault.

`tests/infrastructure/repos/test_django_user_repository.py`

- Uses a fake key provider for the TOTP encryption-at-rest test.
- Confirms stored `totp_secret` ciphertext does not equal the raw TOTP secret and can be decrypted through the repository.
- Earlier repository tests instantiate `DjangoUserRepository()` without a fake provider but do not call TOTP methods, so they do not touch Vault.

`tests/application/identity/test_google_oauth_new_signup.py`

- Uses `DjangoOAuthTokenRepository(key_provider=_KeyProvider())`.
- Verifies Google OAuth access and refresh tokens are not stored as raw plaintext.

`tests/django_app/identity/test_views.py` and `tests/django_app/identity/test_2fa.py`

- Patch identity service construction to use `DjangoUserRepository(key_provider=_KeyProvider())`.
- Cover MFA flows with encrypted TOTP storage without live Vault.

## Operational Implications

- Any runtime path that constructs `VaultKeyProvider()` requires valid Django settings for Vault before the first encrypted field operation.
- Payment command/query handlers are Vault-dependent by default through `payments.infrastructure.factories`.
- Payment webhook retry payload loading is Vault-dependent by default.
- Identity OAuth token save/load and TOTP secret set/get are Vault-dependent by default.
- Identity migrations 0010 and 0011 are Vault-dependent only when plaintext rows exist.
- Production settings intentionally fail fast if Vault config is missing, because production Django and Celery can touch encrypted fields.
- Local/test settings do not fail fast, so local code paths can still fail at runtime if they instantiate the default provider and call encrypted-field operations without a real or injected key provider.
