from __future__ import annotations
from typing import Any

import uuid
from typing import Optional
from django.contrib.auth.hashers import is_password_usable
from django.conf import settings
from django.core.exceptions import ObjectDoesNotExist

from domain.identity.account import AccountStatus, User as DomainUser, UserRole as DomainRole
from domain.identity.credentials import Email, PasswordHash, PasswordHistory
from domain.identity.mfa import TOTPSecret
from application.identity.shared.ports import TotpSecretRepository, AccountRepository
from infrastructure.identity.django_models import password_history_entry_model, user_model


class DjangoUserRepository(AccountRepository, TotpSecretRepository):
    def get_by_id(self, user_id: uuid.UUID) -> Optional[DomainUser]:
        DjangoUser = user_model()
        try:
            user = DjangoUser.objects.get(id=user_id)
        except DjangoUser.DoesNotExist:
            return None
        return self._to_domain(user)

    def get_by_email(self, email: Email) -> Optional[DomainUser]:
        DjangoUser = user_model()
        try:
            user = DjangoUser.objects.get(email__iexact=str(email))
        except DjangoUser.DoesNotExist:
            return None
        return self._to_domain(user)

    def save(self, domain_user: DomainUser) -> DomainUser:
        DjangoUser = user_model()
        previous_password = None
        try:
            django_user = DjangoUser.objects.get(id=domain_user.id)
            previous_password = django_user.password
        except DjangoUser.DoesNotExist:
            django_user = DjangoUser(id=domain_user.id)

        next_password = None
        django_user.email = str(domain_user.email)
        if domain_user.password_hash:
            # The application layer already hashed the password.
            next_password = domain_user.password_hash.reveal_for_password_verification()
            django_user.password = next_password
        else:
            django_user.set_unusable_password()
        django_user.first_name = domain_user.first_name
        django_user.last_name = domain_user.last_name
        django_user.role = domain_user.role.value
        django_user.two_factor_enabled = domain_user.two_factor_enabled
        django_user.auth_token_version = domain_user.auth_token_version
        django_user.is_active = domain_user.is_active
        django_user.is_verified = domain_user.is_verified
        django_user.save()
        if next_password and next_password != previous_password:
            self._remember_password_hash(django_user, next_password)
        return self._to_domain(django_user)

    def get_password_history(self, user_id: uuid.UUID) -> PasswordHistory:
        DjangoUser = user_model()
        DjangoPasswordHistoryEntry = password_history_entry_model()
        try:
            user = DjangoUser.objects.get(id=user_id)
        except DjangoUser.DoesNotExist:
            return PasswordHistory(max_entries=self._password_history_limit())

        hashes = []
        if user.password and is_password_usable(user.password):
            hashes.append(PasswordHash(user.password))
        hashes.extend(
            PasswordHash(entry.password_hash)
            for entry in DjangoPasswordHistoryEntry.objects.filter(user=user).order_by("-created_at")[
                : self._password_history_limit()
            ]
        )
        return PasswordHistory(hashes, max_entries=self._password_history_limit())

    def delete(self, user_id: uuid.UUID) -> None:
        user_model().objects.filter(id=user_id).delete()

    def deactivate(self, user_id: uuid.UUID) -> None:
        user_model().objects.filter(id=user_id).update(is_active=False)

    def _to_domain(self, model: Any) -> DomainUser:
        try:
            role = DomainRole(model.role) if model.role else None
        except (ValueError, TypeError):
            role = None

        return DomainUser(
            id=model.id,
            email=Email(model.email),
            password_hash=PasswordHash(model.password) if model.password and is_password_usable(model.password) else None,
            first_name=model.first_name or "",
            last_name=model.last_name or "",
            role=role,
            two_factor_enabled=model.two_factor_enabled,
            auth_token_version=model.auth_token_version,
            status=self._status_from_model(model),
            is_active=model.is_active,
            is_verified=model.is_verified,
            created_at=model.created_at,
            updated_at=model.updated_at,
            last_login=model.last_login,
        )
    
    def set_totp_secret(self, user_id: uuid.UUID, secret: TOTPSecret) -> None:
        user_model().objects.filter(id=user_id).update(
            totp_secret=secret.reveal_for_totp_verification(),
            two_factor_enabled=True,
        )

    def _status_from_model(self, model: DjangoUser) -> AccountStatus:
        if model.is_active and model.is_verified:
            return AccountStatus.ACTIVE
        if model.is_active:
            return AccountStatus.PENDING_VERIFICATION
        if model.is_verified:
            return AccountStatus.DEACTIVATED
        return AccountStatus.DEACTIVATED_PENDING_VERIFICATION

    def get_totp_secret(self, user_id: uuid.UUID) -> Optional[TOTPSecret]:
        DjangoUser = user_model()
        try:
            user = DjangoUser.objects.get(id=user_id)
            if user.two_factor_enabled and user.totp_secret:
                return TOTPSecret(user.totp_secret)
            return None
        except DjangoUser.DoesNotExist:
            return None

    def clear_totp_secret(self, user_id: uuid.UUID) -> None:
        user_model().objects.filter(id=user_id).update(
            totp_secret=None,
            two_factor_enabled=False,
        )

    def _remember_password_hash(self, user: Any, password_hash: str) -> None:
        DjangoPasswordHistoryEntry = password_history_entry_model()
        DjangoPasswordHistoryEntry.objects.create(user=user, password_hash=password_hash)
        keep_ids = list(
            DjangoPasswordHistoryEntry.objects.filter(user=user)
            .order_by("-created_at")
            .values_list("id", flat=True)[: self._password_history_limit()]
        )
        DjangoPasswordHistoryEntry.objects.filter(user=user).exclude(id__in=keep_ids).delete()

    def _password_history_limit(self) -> int:
        return int(getattr(settings, "PASSWORD_HISTORY_LIMIT", 5))
