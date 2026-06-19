import os
import ssl
from urllib.parse import urlparse, urlunparse

from django.conf import settings
from django.core.exceptions import ImproperlyConfigured
from redis import Redis

VALID_REDIS_SCHEMES = {"redis", "rediss"}
REDIS_SCHEME_ERROR = "REDIS_URL must start with redis:// or rediss://"


def get_redis_url(environ=os.environ) -> str:
    return (environ.get("REDIS_URL") or "").strip()


def validate_redis_url(url: str | None, *, required: bool = False) -> str:
    redis_url = (url or "").strip()
    if not redis_url:
        if required:
            raise ImproperlyConfigured(REDIS_SCHEME_ERROR)
        return ""

    parsed = urlparse(redis_url)
    if parsed.scheme not in VALID_REDIS_SCHEMES:
        raise ImproperlyConfigured(REDIS_SCHEME_ERROR)
    if parsed.scheme in {"redis", "rediss"} and not parsed.netloc:
        raise ImproperlyConfigured(REDIS_SCHEME_ERROR)
    return redis_url


def redis_uses_tls(url: str | None) -> bool:
    return urlparse(url or "").scheme == "rediss"


def redis_ssl_options(url: str | None) -> dict[str, ssl.VerifyMode]:
    if not redis_uses_tls(url):
        return {}
    return {"ssl_cert_reqs": ssl.CERT_REQUIRED}


def get_redis_client(*, optional: bool = False) -> Redis | None:
    try:
        redis_url = validate_redis_url(getattr(settings, "REDIS_URL", ""), required=not optional)
    except ImproperlyConfigured:
        if optional:
            return None
        raise

    if not redis_url:
        return None

    return Redis.from_url(redis_url, **redis_ssl_options(redis_url))


def mask_redis_url(url: str | None) -> str:
    redis_url = (url or "").strip()
    if not redis_url:
        return ""

    parsed = urlparse(redis_url)
    if not parsed.password:
        return redis_url

    username = parsed.username or ""
    auth = f"{username}:***@" if username else "***@"
    host = parsed.hostname or ""
    port = f":{parsed.port}" if parsed.port else ""
    netloc = f"{auth}{host}{port}"
    return urlunparse((parsed.scheme, netloc, parsed.path, parsed.params, parsed.query, parsed.fragment))
