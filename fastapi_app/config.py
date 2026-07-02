import os
import logging
from pathlib import Path
from urllib.parse import parse_qsl, urlencode, urlparse, urlunparse

from dotenv import load_dotenv

BASE_DIR = Path(__file__).resolve().parents[1]
load_dotenv(BASE_DIR / ".env")
logger = logging.getLogger(__name__)

LOCAL_CORS_ORIGINS = [
    "http://localhost:3000",
    "http://127.0.0.1:3000",
]
PRODUCTION_CORS_ORIGINS = [
    "https://www.linkapro.rw",
    "https://linkapro.rw",
    "https://linkapro.vercel.app",
    "https://linkapro-frontend.vercel.app",
]
REQUIRED_PRODUCTION_CORS_ORIGINS = [
    "https://www.linkapro.rw",
    "https://linkapro.rw",
    "https://linkapro.vercel.app",
]
DEFAULT_PRODUCTION_TRUSTED_HOSTS = [
    "linkapro-fastapi.onrender.com",
    "api.linkapro.rw",
]


def get_fastapi_env() -> str:
    return os.getenv("FASTAPI_ENV", "development").strip().lower()


def is_production() -> bool:
    return get_fastapi_env() == "production"


def require_env(name: str) -> str:
    value = os.getenv(name)
    if value is None or not value.strip():
        raise RuntimeError(f"{name} is missing.")
    return value.strip()


def require_bool(name: str) -> bool:
    raw = require_env(name).lower()
    if raw in {"1", "true", "yes", "on"}:
        return True
    if raw in {"0", "false", "no", "off"}:
        return False
    raise RuntimeError(f"{name} must be a boolean value, got {raw!r}.")


def get_bool(name: str, *, default: bool = False) -> bool:
    raw = os.getenv(name)
    if raw is None or not raw.strip():
        return default
    normalized = raw.strip().lower()
    if normalized in {"1", "true", "yes", "on"}:
        return True
    if normalized in {"0", "false", "no", "off"}:
        return False
    raise RuntimeError(f"{name} must be a boolean value, got {normalized!r}.")


def require_int(name: str, *, minimum: int | None = None, maximum: int | None = None) -> int:
    raw = require_env(name)
    try:
        value = int(raw)
    except ValueError as exc:
        raise RuntimeError(f"{name} must be an integer, got {raw!r}.") from exc
    if minimum is not None and value < minimum:
        raise RuntimeError(f"{name} must be >= {minimum}, got {value}.")
    if maximum is not None and value > maximum:
        raise RuntimeError(f"{name} must be <= {maximum}, got {value}.")
    return value


def get_int(name: str, *, default: int, minimum: int | None = None, maximum: int | None = None) -> int:
    raw = os.getenv(name)
    if raw is None or not raw.strip():
        value = default
    else:
        try:
            value = int(raw)
        except ValueError as exc:
            raise RuntimeError(f"{name} must be an integer, got {raw!r}.") from exc
    if minimum is not None and value < minimum:
        raise RuntimeError(f"{name} must be >= {minimum}, got {value}.")
    if maximum is not None and value > maximum:
        raise RuntimeError(f"{name} must be <= {maximum}, got {value}.")
    return value


def get_csv_env(name: str) -> list[str]:
    raw = os.getenv(name, "")
    return [item.strip() for item in raw.split(",") if item.strip()]


def get_cors_origins() -> list[str]:
    configured = [_normalize_origin(origin) for origin in get_csv_env("FASTAPI_CORS_ORIGINS")]
    origins = [origin for origin in configured if origin]

    if is_production():
        missing_required = [origin for origin in REQUIRED_PRODUCTION_CORS_ORIGINS if origin not in origins]
        if missing_required:
            message = (
                "FASTAPI_CORS_ORIGINS must explicitly include required production frontend origins: "
                + ", ".join(missing_required)
            )
            logger.error(message, extra={"missing_origins": missing_required})
            raise RuntimeError(message)
    else:
        origins.extend(origin for origin in LOCAL_CORS_ORIGINS if origin not in origins)
        origins.extend(origin for origin in PRODUCTION_CORS_ORIGINS if origin not in origins)

    return list(dict.fromkeys(origins))


def get_trusted_hosts() -> list[str]:
    configured = get_csv_env("FASTAPI_TRUSTED_HOSTS")
    if not is_production():
        return configured or ["*"]

    hosts = configured or DEFAULT_PRODUCTION_TRUSTED_HOSTS
    cleaned = [host.strip().lower() for host in hosts if host.strip()]
    if not cleaned:
        raise RuntimeError("FASTAPI_TRUSTED_HOSTS must not be empty in production.")
    if "*" in cleaned:
        raise RuntimeError("FASTAPI_TRUSTED_HOSTS must not contain '*' in production.")
    return list(dict.fromkeys(cleaned))


def _normalize_origin(value: str) -> str | None:
    origin = (value or "").strip().rstrip("/")
    if not origin:
        return None
    parsed = urlparse(origin)
    if parsed.scheme not in {"http", "https"} or not parsed.netloc:
        logger.warning("Ignoring invalid CORS origin.", extra={"origin": value})
        return None
    return origin


def normalize_redis_url(redis_url: str, *, production: bool | None = None) -> str:
    url = (redis_url or "").strip().strip('"').strip("'")
    if not url:
        raise RuntimeError("REDIS_URL is missing.")
    parsed = urlparse(url)
    if parsed.scheme not in {"redis", "rediss"}:
        raise RuntimeError("REDIS_URL must start with redis:// or rediss://.")

    query = dict(parse_qsl(parsed.query, keep_blank_values=True))
    if parsed.scheme == "rediss":
        cert_reqs = query.get("ssl_cert_reqs")
        if cert_reqs == "CERT_REQUIRED":
            query["ssl_cert_reqs"] = "required"
        elif not cert_reqs:
            query["ssl_cert_reqs"] = "required"
        elif cert_reqs.lower() == "cert_none" or cert_reqs.lower() == "none":
            is_prod = production if production is not None else is_production()
            if is_prod:
                raise RuntimeError("REDIS_URL must not use ssl_cert_reqs=none in production.")
    return urlunparse(parsed._replace(query=urlencode(query)))


def mask_redis_url_for_logs(redis_url: str) -> str:
    parsed = urlparse(redis_url or "")
    if not parsed.netloc:
        return "<invalid-redis-url>"
    hostname = parsed.hostname or ""
    port = f":{parsed.port}" if parsed.port else ""
    username = f"{parsed.username}:***@" if parsed.username else ""
    return urlunparse(parsed._replace(netloc=f"{username}{hostname}{port}", query=""))


def normalize_database_url(database_url: str) -> str:
    url = (database_url or "").strip()
    if not url:
        raise RuntimeError("FASTAPI_DATABASE_URL is missing.")
    if url.startswith("postgres://"):
        return url.replace("postgres://", "postgresql+asyncpg://", 1)
    if url.startswith("postgresql://"):
        return url.replace("postgresql://", "postgresql+asyncpg://", 1)
    if not url.startswith("postgresql+asyncpg://"):
        raise RuntimeError("FASTAPI_DATABASE_URL must use postgresql+asyncpg://")
    return url


def get_database_engine_options(database_url: str) -> dict:
    options: dict = {
        "echo": get_bool("FASTAPI_SQL_ECHO", default=False),
        "future": True,
    }

    if database_url.startswith("postgresql+asyncpg://"):
        options.update(
            {
                "pool_pre_ping": True,
                "pool_recycle": get_int("FASTAPI_DB_POOL_RECYCLE_SECONDS", default=1800, minimum=60),
                "pool_size": get_int("FASTAPI_DB_POOL_SIZE", default=5, minimum=1, maximum=50),
                "max_overflow": get_int("FASTAPI_DB_MAX_OVERFLOW", default=5, minimum=0, maximum=100),
                "pool_timeout": get_int("FASTAPI_DB_POOL_TIMEOUT_SECONDS", default=10, minimum=1, maximum=120),
            }
        )

    return options
