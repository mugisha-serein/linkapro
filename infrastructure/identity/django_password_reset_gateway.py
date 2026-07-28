"""Django gateway for password reset completion."""
from __future__ import annotations

from django.db import transaction
from django.conf import settings
from django.contrib.auth.hashers import check_password

from application.identity.recovery import PasswordResetVerification
from domain.identity.credentials import PasswordHash, PasswordHistory, PlainPassword
from domain.identity.recovery import PasswordResetToken, PasswordResetTokenStatus
from django_app.identity.models import PasswordHistoryEntry as DjangoPasswordHistoryEntry
from django_app.identity.models import PasswordResetToken as DjangoPasswordResetToken
from django_app.identity.models import User
from infrastructure.identity.django_identity_event_outbox import DjangoIdentityEventOutboxDispatcher
from infrastructure.identity.jwt_token_service import (
    JWTTokenService,
    password_reset_token_hash,
    password_reset_value_hash,
)


class DjangoPasswordResetGateway:
    def __init__(
        self,
        *,
        token_service: JWTTokenService | None = None,
        event_dispatcher: DjangoIdentityEventOutboxDispatcher | None = None,
    ):
        self.token_service = token_service or JWTTokenService()
        self.event_dispatcher = event_dispatcher or DjangoIdentityEventOutboxDispatcher()

    def complete_in_transaction(self, operation):
        with transaction.atomic():
            return operation()

    def verify_reset_token(self, raw_token: str) -> PasswordResetVerification | None:
        payload = self.token_service.decode_password_reset_token_payload(raw_token)
        if not payload:
            return None
        token_record = (
            DjangoPasswordResetToken.objects.select_for_update()
            .filter(
                user_id=payload.get("user_id"),
                jti=payload.get("jti"),
                token_hash=password_reset_token_hash(raw_token),
            )
            .first()
        )
        if not token_record:
            return None
        return PasswordResetVerification(
            user_id=token_record.user_id,
            token=self._to_domain(token_record),
        )

    def mark_token_expired(self, token: PasswordResetToken, *, now) -> None:
        DjangoPasswordResetToken.objects.filter(id=token.id).update(
            status=DjangoPasswordResetToken.Status.EXPIRED,
            updated_at=now,
        )

    def get_active_user_for_update(self, user_id):
        return User.objects.select_for_update().filter(id=user_id, is_active=True).first()

    def get_password_history(self, user) -> PasswordHistory:
        limit = self._history_limit()
        hashes = []
        if user.password:
            hashes.append(PasswordHash(user.password))
        hashes.extend(
            PasswordHash(entry.password_hash)
            for entry in DjangoPasswordHistoryEntry.objects.filter(user=user).order_by("-created_at")[:limit]
        )
        return PasswordHistory(hashes, max_entries=limit)

    def password_matches(self, plain_password: PlainPassword, password_hash: PasswordHash) -> bool:
        return check_password(
            plain_password.value,
            password_hash.reveal_for_password_verification(),
        )

    def set_user_password(self, user, new_password: str) -> PasswordHash:
        user.set_password(new_password)
        user.save(update_fields=["password", "updated_at"])
        return PasswordHash(user.password)

    def remember_password_hash(self, *, user, password_hash: PasswordHash, now) -> None:
        DjangoPasswordHistoryEntry.objects.create(
            user=user,
            password_hash=password_hash.reveal_for_password_verification(),
            created_at=now,
        )
        self._prune_password_history(user)

    def persist_used_token(self, token: PasswordResetToken) -> None:
        DjangoPasswordResetToken.objects.filter(id=token.id).update(
            status=DjangoPasswordResetToken.Status.USED,
            used_at=token.used_at,
            used_ip_hash=token.used_ip_hash,
            used_user_agent_hash=token.used_user_agent_hash,
            updated_at=token.used_at,
        )

    def revoke_other_active_tokens(self, *, user, exclude_token_id, now) -> None:
        DjangoPasswordResetToken.objects.filter(
            user=user,
            status=DjangoPasswordResetToken.Status.ACTIVE,
        ).exclude(id=exclude_token_id).update(
            status=DjangoPasswordResetToken.Status.REVOKED,
            updated_at=now,
        )

    def dispatch_password_changed(self, event) -> None:
        self.event_dispatcher.dispatch(event)

    def hash_reset_value(self, value: str) -> str:
        return password_reset_value_hash(value)

    def _history_limit(self) -> int:
        return int(getattr(settings, "PASSWORD_HISTORY_LIMIT", 5))

    def _prune_password_history(self, user) -> None:
        keep_ids = list(
            DjangoPasswordHistoryEntry.objects.filter(user=user)
            .order_by("-created_at")
            .values_list("id", flat=True)[: self._history_limit()]
        )
        DjangoPasswordHistoryEntry.objects.filter(user=user).exclude(id__in=keep_ids).delete()

    @staticmethod
    def _to_domain(record: DjangoPasswordResetToken) -> PasswordResetToken:
        return PasswordResetToken(
            id=record.id,
            user_id=record.user_id,
            jti=record.jti,
            token_hash=record.token_hash,
            status=PasswordResetTokenStatus(record.status),
            expires_at=record.expires_at,
            used_at=record.used_at,
            used_ip_hash=record.used_ip_hash,
            used_user_agent_hash=record.used_user_agent_hash,
        )
