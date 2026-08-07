# Encrypt TOTP secrets at rest using Vault-backed envelope encryption.
#
# Replaces the empty 0011_encrypt_totp_secret stub with a real migration.
# The final column keeps the historical name `totp_secret` but stores the
# encrypted JSON payload (ciphertext/iv/tag/dek_encrypted) instead of the raw
# base32 secret. Vault is only contacted when plaintext rows exist; empty
# tables migrate without Vault configuration.
#
# NOTE: This migration is intentionally one-way. The reverse operation is a
# noop and the RemoveField/RenameField operations discard the plaintext form,
# so existing data is only recoverable from the encrypted form (or a database
# backup taken before applying this migration).

import json
import secrets

from django.db import migrations, models


def _encrypt_existing_totp_secrets(apps, schema_editor):
    User = apps.get_model("identity", "User")
    rows = list(
        User.objects.exclude(totp_secret__isnull=True).exclude(totp_secret="")
    )
    if not rows:
        return

    from payments.infrastructure.crypto import encrypt_field
    from payments.helpers.encryption import encrypted_field_to_json
    from payments.infrastructure.vault_key_provider import VaultKeyProvider
    from payments.domain.value_objects import EncryptedField

    provider = VaultKeyProvider()
    for row in rows:
        dek = secrets.token_bytes(32)
        wrapped_dek = provider.wrap_dek(dek)
        encrypted = encrypt_field(row.totp_secret.encode("utf-8"), dek)
        encrypted_with_dek = EncryptedField(
            ciphertext=encrypted.ciphertext,
            iv=encrypted.iv,
            tag=encrypted.tag,
            dek_encrypted=wrapped_dek,
        )
        row._encrypted_totp_secret = json.dumps(encrypted_field_to_json(encrypted_with_dek))
        row.save(update_fields=["_encrypted_totp_secret"])


class Migration(migrations.Migration):
    dependencies = [
        ("identity", "0013_encrypt_oauth_tokens"),
    ]

    operations = [
        migrations.AddField(
            model_name="user",
            name="_encrypted_totp_secret",
            field=models.TextField(blank=True, null=True),
        ),
        migrations.RunPython(_encrypt_existing_totp_secrets, migrations.RunPython.noop),
        migrations.RemoveField(
            model_name="user",
            name="totp_secret",
        ),
        migrations.RenameField(
            model_name="user",
            old_name="_encrypted_totp_secret",
            new_name="totp_secret",
        ),
    ]
