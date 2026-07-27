from django.contrib.auth.hashers import check_password, make_password

from application.identity.ports import ITokenBlacklist
from django_app.common.redis_config import get_redis_client
from domain.identity.value_objects import PasswordHash, PlainPassword


class DjangoPasswordHasher:
    def hash(self, plain: PlainPassword) -> str:
        return make_password(plain.value)

    def verify(self, plain: PlainPassword | str, hashed: PasswordHash) -> bool:
        candidate = plain.value if hasattr(plain, "value") else str(plain)
        return check_password(candidate, hashed.reveal_for_password_verification())


class RedisTokenBlacklist(ITokenBlacklist):
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
