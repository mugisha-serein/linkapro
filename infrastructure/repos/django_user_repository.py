import uuid
from typing import Optional
from django.contrib.auth.hashers import is_password_usable
from django.core.exceptions import ObjectDoesNotExist

from domain.identity.entities import User as DomainUser, UserRole as DomainRole
from domain.identity.value_objects import Email, PasswordHash
from domain.identity.interfaces import IUserRepository
from django_app.identity.models import User as DjangoUser


class DjangoUserRepository(IUserRepository):
    def get_by_id(self, user_id: uuid.UUID) -> Optional[DomainUser]:
        try:
            user = DjangoUser.objects.get(id=user_id)
            return self._to_domain(user)
        except ObjectDoesNotExist:
            return None

    def get_by_email(self, email: Email) -> Optional[DomainUser]:
        try:
            user = DjangoUser.objects.get(email=str(email))
            return self._to_domain(user)
        except ObjectDoesNotExist:
            return None

    def save(self, domain_user: DomainUser) -> DomainUser:
        try:
            django_user = DjangoUser.objects.get(id=domain_user.id)
        except DjangoUser.DoesNotExist:
            django_user = DjangoUser(id=domain_user.id)

        django_user.email = str(domain_user.email)
        if domain_user.password_hash:
            django_user.password = str(domain_user.password_hash)
        elif not django_user.password:
            django_user.set_unusable_password()
        django_user.first_name = domain_user.first_name
        django_user.last_name = domain_user.last_name
        django_user.role = domain_user.role.value
        django_user.two_factor_enabled = domain_user.two_factor_enabled
        django_user.auth_token_version = domain_user.auth_token_version
        django_user.is_active = domain_user.is_active
        django_user.is_verified = domain_user.is_verified
        django_user.save()
        return self._to_domain(django_user)

    def delete(self, user_id: uuid.UUID) -> None:
        DjangoUser.objects.filter(id=user_id).delete()

    def _to_domain(self, model: DjangoUser) -> DomainUser:
        return DomainUser(
            id=model.id,
            email=Email(model.email),
            password_hash=PasswordHash(model.password) if model.password and is_password_usable(model.password) else None,
            first_name=model.first_name,
            last_name=model.last_name,
            role=DomainRole(model.role),
            two_factor_enabled=model.two_factor_enabled,
            auth_token_version=model.auth_token_version,
            is_active=model.is_active,
            is_verified=model.is_verified,
            created_at=model.created_at,
            updated_at=model.updated_at,
            last_login=model.last_login,
        )
    
    def set_totp_secret(self, user_id: uuid.UUID, secret: str) -> None:
        DjangoUser.objects.filter(id=user_id).update(totp_secret=secret, two_factor_enabled=True)

    def get_totp_secret(self, user_id: uuid.UUID) -> Optional[str]:
        try:
            user = DjangoUser.objects.get(id=user_id)
            return user.totp_secret if user.two_factor_enabled else None
        except DjangoUser.DoesNotExist:
            return None
