from django.contrib.auth.hashers import check_password, make_password
from django.utils import timezone

from application.identity.shared.dtos import MfaLoginGrant
from application.identity.shared.ports import TokenRevocationStore, PasswordHasher
from django_app.common.redis_config import get_redis_client
from domain.identity.credentials import PasswordHash, PlainPassword


_DUMMY_PASSWORD_HASH = make_password("LinkaproDummyPassword1!")


class DjangoPasswordHasher(PasswordHasher):
    def hash(self, plain: PlainPassword) -> str:
        return make_password(plain.value)

    def verify(self, plain: PlainPassword | str, hashed: PasswordHash) -> bool:
        candidate = plain.value if hasattr(plain, "value") else str(plain)
        return check_password(candidate, hashed.reveal_for_password_verification())

    def verify_against_dummy(self, password: PlainPassword) -> None:
        candidate = password.value if hasattr(password, "value") else str(password)
        check_password(candidate, _DUMMY_PASSWORD_HASH)


class RedisTokenBlacklist(TokenRevocationStore):
    def __init__(self):
        self.client = get_redis_client()

    def is_blacklisted(self, jti: str) -> bool:
        return bool(self.client.exists(f"bl:{jti}"))

    def blacklist(self, jti: str, ttl: int) -> None:
        self.client.setex(f"bl:{jti}", ttl, "1")

    def is_family_blacklisted(self, family_id: str) -> bool:
        return bool(self.client.exists(f"family:{family_id}"))

    def blacklist_family(self, family_id: str) -> None:
        # Individual tokens check both jti and family blacklist.
        self.client.setex(f"family:{family_id}", 7 * 24 * 3600, "1")

    def is_mfa_grant_blacklisted(self, grant: MfaLoginGrant) -> bool:
        return self.is_blacklisted(grant.grant_id)

    def blacklist_mfa_grant(self, grant: MfaLoginGrant) -> None:
        self.blacklist(
            grant.grant_id,
            ttl=grant.remaining_ttl_seconds(now=timezone.now()),
        )
