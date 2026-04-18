from datetime import datetime, timezone

UTC = timezone.utc

def utc_now() -> datetime:
    """Return current UTC datetime with timezone awareness."""
    return datetime.now(UTC)