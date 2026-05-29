import redis
from django.conf import settings
from payments.application.ports import ITokenBlacklist


class RedisTokenBlacklist(ITokenBlacklist):
    def __init__(self):
        self.client = redis.Redis.from_url(settings.REDIS_URL)

    def is_blacklisted(self, jti: str) -> bool:
        return bool(self.client.exists(f"bl:{jti}"))

    def blacklist(self, jti: str, ttl: int) -> None:
        self.client.setex(f"bl:{jti}", ttl, "1")

    def is_family_blacklisted(self, family_id: str) -> bool:
        return bool(self.client.exists(f"family:{family_id}"))

    def blacklist_family(self, family_id: str) -> None:
        # Invalidate all tokens in family by storing a family-level blacklist entry
        # Individual tokens check both jti and family blacklist.
        self.client.setex(f"family:{family_id}", 7 * 24 * 3600, "1")  # 7 days
