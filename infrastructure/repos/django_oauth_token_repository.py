import uuid
from typing import Optional
from django.core.exceptions import ObjectDoesNotExist

from domain.identity.entities import OAuthToken as DomainToken
from domain.identity.value_objects import OAuthProvider
from domain.identity.interfaces import IOAuthTokenRepository
from django_app.identity.models import OAuthToken as DjangoToken, User as DjangoUser


class DjangoOAuthTokenRepository(IOAuthTokenRepository):
    def get_by_provider_and_user(self, provider: OAuthProvider, provider_user_id: str) -> Optional[DomainToken]:
        try:
            token = DjangoToken.objects.get(
                provider=provider.value,
                provider_user_id=provider_user_id
            )
            return self._to_domain(token)
        except ObjectDoesNotExist:
            return None

    def save(self, domain_token: DomainToken) -> DomainToken:
        try:
            django_token = DjangoToken.objects.get(id=domain_token.id)
        except DjangoToken.DoesNotExist:
            django_token = DjangoToken(id=domain_token.id)

        django_token.user = DjangoUser.objects.get(id=domain_token.user_id)
        django_token.provider = domain_token.provider.value
        django_token.provider_user_id = domain_token.provider_user_id
        django_token.access_token = domain_token.access_token
        django_token.refresh_token = domain_token.refresh_token
        django_token.expires_at = domain_token.expires_at
        django_token.created_at = domain_token.created_at
        django_token.save()
        return self._to_domain(django_token)

    def get_by_user_and_provider(self, user_id: uuid.UUID, provider: OAuthProvider) -> Optional[DomainToken]:
        token = (
            DjangoToken.objects.filter(user_id=user_id, provider=provider.value)
            .order_by("created_at")
            .first()
        )
        if not token:
            return None
        return self._to_domain(token)

    def delete_for_user(self, user_id: uuid.UUID, provider: OAuthProvider) -> None:
        DjangoToken.objects.filter(user_id=user_id, provider=provider.value).delete()

    def _to_domain(self, model: DjangoToken) -> DomainToken:
        return DomainToken(
            id=model.id,
            user_id=model.user_id,
            provider=OAuthProvider(model.provider),
            provider_user_id=model.provider_user_id,
            access_token=model.access_token,
            refresh_token=model.refresh_token,
            expires_at=model.expires_at,
            created_at=model.created_at,
        )
