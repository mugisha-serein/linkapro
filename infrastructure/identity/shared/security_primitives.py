import ssl
from urllib.parse import urlparse

from django.contrib.auth.hashers import check_password, make_password
from django.conf import settings
from django.core.exceptions import ImproperlyConfigured
from django.utils import timezone
from redis import Redis

from application.identity.shared.dtos import MfaLoginGrant
from application.identity.shared.ports import TokenRevocationStore, PasswordHasher
from domain.identity.credentials import PasswordHash, PlainPassword


_DUMMY_PASSWORD_HASH = make_password("LinkaproDummyPassword1!")
_VALID_REDIS_SCHEMES = {"redis", "rediss"}
_REDIS_SCHEME_ERROR = "REDIS_URL must start with redis:// or rediss://"


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
        self.client = _get_redis_client()

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


def _get_redis_client() -> Redis:
    redis_url = _validate_redis_url(getattr(settings, "REDIS_URL", ""))
    return Redis.from_url(redis_url, **_redis_ssl_options(redis_url))


def _validate_redis_url(url: str | None) -> str:
    redis_url = (url or "").strip()
    if not redis_url:
        raise ImproperlyConfigured(_REDIS_SCHEME_ERROR)

    parsed = urlparse(redis_url)
    if parsed.scheme not in _VALID_REDIS_SCHEMES or not parsed.netloc:
        raise ImproperlyConfigured(_REDIS_SCHEME_ERROR)
    return redis_url


def _redis_ssl_options(url: str | None) -> dict[str, ssl.VerifyMode]:
    return {"ssl_cert_reqs": ssl.CERT_REQUIRED} if urlparse(url or "").scheme == "rediss" else {}
