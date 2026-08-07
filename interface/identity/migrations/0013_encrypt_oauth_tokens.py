# Encrypt OAuth access/refresh tokens at rest using Vault-backed envelope encryption.
#
# Replaces the empty 0010_encrypt_oauth_tokens stub with a real migration.
# Existing plaintext rows are encrypted with a per-row DEK wrapped by Vault
# Transit. Vault is only contacted when plaintext rows exist; empty tables
# migrate without Vault configuration.
#
# NOTE: This migration is intentionally one-way. The reverse operation is a
# noop and the RemoveField operations drop the plaintext columns, so existing
# data is only recoverable from the encrypted form (or a database backup taken
# before applying this migration).

import json
import secrets

from django.db import migrations, models


def _encrypt_existing_oauth_tokens(apps, schema_editor):
    OAuthToken = apps.get_model("identity", "OAuthToken")
    rows = list(
        OAuthToken.objects.exclude(access_token__isnull=True).exclude(access_token="")
    )
    if not rows:
        return

    from payments.infrastructure.crypto import encrypt_field
    from payments.helpers.encryption import encrypted_field_to_json
    from payments.infrastructure.vault_key_provider import VaultKeyProvider

    provider = VaultKeyProvider()
    for row in rows:
        dek = secrets.token_bytes(32)
        wrapped_dek = provider.wrap_dek(dek)
        encrypted_access = encrypt_field(row.access_token.encode("utf-8"), dek)
        row.encrypted_access_token = json.dumps(encrypted_field_to_json(encrypted_access))
        if row.refresh_token:
            encrypted_refresh = encrypt_field(row.refresh_token.encode("utf-8"), dek)
            row.encrypted_refresh_token = json.dumps(encrypted_field_to_json(encrypted_refresh))
        row.dek_encrypted = wrapped_dek
        row.save(
            update_fields=[
                "encrypted_access_token",
                "encrypted_refresh_token",
                "dek_encrypted",
            ]
        )


class Migration(migrations.Migration):
    dependencies = [
        ("identity", "0012_passwordhistoryentry"),
    ]

    operations = [
        migrations.AddField(
            model_name="oauthtoken",
            name="encrypted_access_token",
            field=models.TextField(blank=True, null=True),
        ),
        migrations.AddField(
            model_name="oauthtoken",
            name="encrypted_refresh_token",
            field=models.TextField(blank=True, null=True),
        ),
        migrations.AddField(
            model_name="oauthtoken",
            name="dek_encrypted",
            field=models.BinaryField(blank=True, null=True),
        ),
        migrations.RunPython(_encrypt_existing_oauth_tokens, migrations.RunPython.noop),
        migrations.RemoveField(
            model_name="oauthtoken",
            name="access_token",
        ),
        migrations.RemoveField(
            model_name="oauthtoken",
            name="refresh_token",
        ),
    ]
