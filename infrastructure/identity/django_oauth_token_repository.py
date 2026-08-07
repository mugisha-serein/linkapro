from __future__ import annotations

import json
import logging
import secrets
import uuid
from typing import Optional
from django.core.exceptions import ObjectDoesNotExist

from domain.identity.oauth import OAuthToken as DomainToken
from domain.identity.oauth import OAuthAccessToken, OAuthProvider, OAuthRefreshToken
from application.identity.shared.ports import OAuthIdentityRepository
from payments.application.ports import IKeyProvider
from payments.helpers.encryption import (
    encrypted_field_from_json,
    encrypted_field_to_json,
    is_encrypted_payload,
)
from payments.infrastructure.crypto import decrypt_field, encrypt_field
from payments.infrastructure.vault_key_provider import VaultKeyProvider
from infrastructure.identity.django_models import oauth_token_model, user_model


logger = logging.getLogger(__name__)


class DjangoOAuthTokenRepository(OAuthIdentityRepository):
    def __init__(self, key_provider: IKeyProvider | None = None) -> None:
        self.key_provider = key_provider or VaultKeyProvider()

    def get_by_provider_and_user(self, provider: OAuthProvider, provider_user_id: str) -> Optional[DomainToken]:
        DjangoToken = oauth_token_model()
        try:
            token = DjangoToken.objects.get(
                provider=provider.value,
                provider_user_id=provider_user_id
            )
            return self._to_domain(token)
        except ObjectDoesNotExist:
            return None

    def save(self, domain_token: DomainToken) -> DomainToken:
        DjangoToken = oauth_token_model()
        try:
            django_token = DjangoToken.objects.get(id=domain_token.id)
        except DjangoToken.DoesNotExist:
            django_token = DjangoToken(id=domain_token.id)

        django_token.user = user_model().objects.get(id=domain_token.user_id)
        django_token.provider = domain_token.provider.value
        django_token.provider_user_id = domain_token.provider_user_id
        dek = secrets.token_bytes(32)
        wrapped_dek = self.key_provider.wrap_dek(dek)
        encrypted_access = encrypt_field(domain_token.access_token.raw_value.encode("utf-8"), dek)
        django_token.encrypted_access_token = json.dumps(encrypted_field_to_json(encrypted_access))
        if domain_token.refresh_token:
            encrypted_refresh = encrypt_field(domain_token.refresh_token.raw_value.encode("utf-8"), dek)
            django_token.encrypted_refresh_token = json.dumps(encrypted_field_to_json(encrypted_refresh))
        else:
            django_token.encrypted_refresh_token = None
        django_token.dek_encrypted = wrapped_dek
        django_token.expires_at = domain_token.expires_at
        django_token.created_at = domain_token.created_at
        django_token.save()
        return self._to_domain(django_token)

    def get_by_user_and_provider(self, user_id: uuid.UUID, provider: OAuthProvider) -> Optional[DomainToken]:
        token = (
            oauth_token_model().objects.filter(user_id=user_id, provider=provider.value)
            .order_by("created_at")
            .first()
        )
        if not token:
            return None
        return self._to_domain(token)

    def list_by_user(self, user_id: uuid.UUID) -> tuple[DomainToken, ...]:
        tokens = oauth_token_model().objects.filter(user_id=user_id).order_by("provider", "created_at")
        return tuple(self._to_domain(token) for token in tokens)

    def delete_for_user(self, user_id: uuid.UUID, provider: OAuthProvider) -> None:
        oauth_token_model().objects.filter(user_id=user_id, provider=provider.value).delete()

    def _to_domain(self, model: DjangoToken) -> DomainToken:
        access_raw = self._decrypt_token(model, "encrypted_access_token")
        if access_raw is None:
            raise ValueError("Encrypted OAuth access token is missing")
        return DomainToken(
            id=model.id,
            user_id=model.user_id,
            provider=OAuthProvider(model.provider),
            provider_user_id=model.provider_user_id,
            access_token=OAuthAccessToken(access_raw),
            refresh_token=(
                OAuthRefreshToken(self._decrypt_token(model, "encrypted_refresh_token"))
                if model.encrypted_refresh_token
                else None
            ),
            expires_at=model.expires_at,
            created_at=model.created_at,
        )

    def _decrypt_token(self, model: DjangoToken, field_name: str) -> Optional[str]:
        raw_value = getattr(model, field_name)
        if not raw_value:
            return None
        try:
            payload = json.loads(raw_value)
        except (TypeError, ValueError):
            # Legacy plaintext value written before at-rest encryption was enabled.
            logger.warning(
                "oauth_token_plaintext_value_detected",
                extra={"token_id": str(model.id), "field": field_name},
            )
            return raw_value
        if not is_encrypted_payload(payload):
            logger.warning(
                "oauth_token_plaintext_value_detected",
                extra={"token_id": str(model.id), "field": field_name},
            )
            return raw_value
        try:
            encrypted = encrypted_field_from_json(payload)
            dek = self.key_provider.unwrap_dek(model.dek_encrypted)
            return decrypt_field(encrypted, dek).decode("utf-8")
        except Exception as exc:
            # Raise loudly rather than silently treating a corrupted or tampered
            # ciphertext as a missing link during Google OAuth flows.
            logger.error(
                "oauth_token_decrypt_failed",
                extra={"token_id": str(model.id), "field": field_name, "error_type": exc.__class__.__name__},
                exc_info=True,
            )
            raise ValueError("Stored OAuth token cannot be decrypted") from exc
