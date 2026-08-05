from __future__ import annotations

import uuid
from typing import Optional
from django.core.exceptions import ObjectDoesNotExist

from domain.identity.oauth import OAuthToken as DomainToken
from domain.identity.oauth import OAuthAccessToken, OAuthProvider, OAuthRefreshToken
from application.identity.shared.ports import OAuthIdentityRepository
from infrastructure.identity.django_models import oauth_token_model, user_model


class DjangoOAuthTokenRepository(OAuthIdentityRepository):
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
        django_token.access_token = domain_token.access_token.raw_value
        django_token.refresh_token = domain_token.refresh_token.raw_value if domain_token.refresh_token else None
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
        return DomainToken(
            id=model.id,
            user_id=model.user_id,
            provider=OAuthProvider(model.provider),
            provider_user_id=model.provider_user_id,
            access_token=OAuthAccessToken(model.access_token),
            refresh_token=(
                OAuthRefreshToken(model.refresh_token)
                if model.refresh_token
                else None
            ),
            expires_at=model.expires_at,
            created_at=model.created_at,
        )
