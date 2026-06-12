import os
import logging
from pathlib import Path
from urllib.parse import urlparse

from dotenv import load_dotenv

BASE_DIR = Path(__file__).resolve().parents[1]
load_dotenv(BASE_DIR / ".env")
logger = logging.getLogger(__name__)

LOCAL_CORS_ORIGINS = [
    "http://localhost:3000",
    "http://127.0.0.1:3000",
]
PRODUCTION_CORS_ORIGINS = [
    "https://linkapro.vercel.app",
    "https://linkapro-frontend.vercel.app",
]


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


def get_cors_origins() -> list[str]:
    raw = os.getenv("FASTAPI_CORS_ORIGINS", "")
    env_name = os.getenv("FASTAPI_ENV", "development").strip().lower()
    configured = [_normalize_origin(origin) for origin in raw.split(",")]
    origins = [origin for origin in configured if origin]

    if env_name == "production":
        missing_required = [origin for origin in PRODUCTION_CORS_ORIGINS if origin not in origins]
        if missing_required:
            message = (
                "FASTAPI_CORS_ORIGINS must explicitly include production frontend origins: "
                + ", ".join(PRODUCTION_CORS_ORIGINS)
            )
            logger.error(message, extra={"missing_origins": missing_required})
            raise RuntimeError(message)
    else:
        origins.extend(origin for origin in LOCAL_CORS_ORIGINS if origin not in origins)
        origins.extend(origin for origin in PRODUCTION_CORS_ORIGINS if origin not in origins)

    return list(dict.fromkeys(origins))


def _normalize_origin(value: str) -> str | None:
    origin = (value or "").strip().rstrip("/")
    if not origin:
        return None
    parsed = urlparse(origin)
    if parsed.scheme not in {"http", "https"} or not parsed.netloc:
        logger.warning("Ignoring invalid CORS origin.", extra={"origin": value})
        return None
    return origin
