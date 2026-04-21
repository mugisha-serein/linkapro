import uuid
from typing import Optional
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
            django_user.set_password(str(domain_user.password_hash))
        else:
            django_user.password = None  # OAuth users have no password
        django_user.first_name = domain_user.first_name
        django_user.last_name = domain_user.last_name
        django_user.role = domain_user.role.value
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
            password_hash=PasswordHash(model.password) if model.password else None,
            first_name=model.first_name,
            last_name=model.last_name,
            role=DomainRole(model.role),
            is_active=model.is_active,
            is_verified=model.is_verified,
            created_at=model.created_at,
            updated_at=model.updated_at,
            last_login=model.last_login,
        )