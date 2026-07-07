from __future__ import annotations

import re
import uuid
from datetime import datetime, timezone
from decimal import Decimal, InvalidOperation
from urllib.parse import urlparse

TEXT_LIMITS = {
    "business_name": 200,
    "description": 5000,
    "service_area": 255,
    "contact_email": 254,
    "contact_phone": 20,
    "custom_category": 100,
    "website": 500,
    "profile_image_url": 1000,
    "cover_image_url": 1000,
    "package_name": 200,
    "package_description": 5000,
    "caption": 500,
    "rejection_reason": 1000,
    "client_name": 200,
    "message": 5000,
    "public_id": 255,
}

MIN_PACKAGE_DESCRIPTION_LENGTH = 10
MIN_INQUIRY_MESSAGE_LENGTH = 3
MAX_PORTFOLIO_ORDER = 10_000
MAX_PACKAGE_PRICE = Decimal("9999999999.99")
PACKAGE_PRICE_SCALE = 2
SUPPORTED_CURRENCIES = {"RWF", "USD", "EUR", "KES", "GHS", "NGN"}

_EMAIL_RE = re.compile(r"^[^@\s]+@[^@\s]+\.[^@\s]+$")
_CONTROL_RE = re.compile(r"[\x00-\x1f\x7f]")
_PHONE_ALLOWED_RE = re.compile(r"^[+]?[0-9]{3,20}$")


def has_control_characters(value: str) -> bool:
    return bool(_CONTROL_RE.search(value or ""))


def bounded_text(
    value,
    *,
    field_name: str,
    max_length: int,
    min_length: int = 1,
    required: bool = True,
) -> str | None:
    if value is None:
        if required:
            raise ValueError("This field is required.")
        return None
    text = str(value).strip()
    if not text:
        if required:
            raise ValueError("This field is required.")
        return ""
    if has_control_characters(text):
        raise ValueError("Control characters are not allowed.")
    if len(text) < min_length:
        raise ValueError(f"Use at least {min_length} characters.")
    if len(text) > max_length:
        raise ValueError(f"Use {max_length} characters or fewer.")
    return text


def validate_email(value, *, field_name: str = "email") -> str:
    email = bounded_text(
        value,
        field_name=field_name,
        max_length=TEXT_LIMITS["contact_email"],
    )
    if not _EMAIL_RE.match(email):
        raise ValueError("Enter a valid email address.")
    return email.lower()


def normalize_phone(value, *, required: bool = True) -> str | None:
    phone = bounded_text(
        value,
        field_name="phone",
        max_length=TEXT_LIMITS["contact_phone"],
        required=required,
    )
    if phone is None or phone == "":
        return phone
    normalized = re.sub(r"[\s().-]+", "", phone)
    if not _PHONE_ALLOWED_RE.match(normalized):
        raise ValueError("Enter a valid phone number.")
    return normalized


def validate_safe_url(value, *, field_name: str, required: bool = False) -> str | None:
    url = bounded_text(
        value,
        field_name=field_name,
        max_length=TEXT_LIMITS.get(field_name, 1000),
        required=required,
    )
    if url is None or url == "":
        return url
    parsed = urlparse(url)
    if parsed.scheme not in {"http", "https"} or not parsed.netloc:
        raise ValueError("Enter a valid HTTP or HTTPS URL.")
    return url


def validate_public_media_url(value, *, field_name: str, required: bool = False) -> str | None:
    url = validate_safe_url(value, field_name=field_name, required=required)
    if url and urlparse(url).scheme != "https":
        raise ValueError("Public media URLs must use HTTPS.")
    return url


def validate_uuid(value, *, field_name: str) -> uuid.UUID:
    if isinstance(value, uuid.UUID):
        return value
    try:
        return uuid.UUID(str(value))
    except (TypeError, ValueError, AttributeError):
        raise ValueError("Enter a valid UUID.") from None


def aware_utc_datetime(value, *, field_name: str, required: bool = False) -> datetime | None:
    if value is None:
        if required:
            raise ValueError("This timestamp is required.")
        return None
    if not isinstance(value, datetime):
        raise ValueError("Enter a valid datetime.")
    if value.tzinfo is None or value.utcoffset() is None:
        raise ValueError("Datetime must be timezone-aware.")
    return value.astimezone(timezone.utc)


def positive_decimal(value, *, field_name: str = "price") -> Decimal:
    try:
        amount = Decimal(str(value))
    except (InvalidOperation, TypeError, ValueError):
        raise ValueError("Enter a valid decimal amount.") from None
    if not amount.is_finite():
        raise ValueError("Enter a finite decimal amount.")
    if amount <= 0:
        raise ValueError("Amount must be greater than 0.")
    if amount.as_tuple().exponent < -PACKAGE_PRICE_SCALE:
        raise ValueError(f"Use no more than {PACKAGE_PRICE_SCALE} decimal places.")
    if amount > MAX_PACKAGE_PRICE:
        raise ValueError(f"Amount must be no more than {MAX_PACKAGE_PRICE}.")
    return amount


def normalize_currency(value) -> str:
    currency = bounded_text(value, field_name="currency", max_length=3)
    normalized = currency.upper()
    if normalized not in SUPPORTED_CURRENCIES:
        raise ValueError("Choose a supported currency.")
    return normalized


def add_error(errors: dict[str, list[str]], field: str, message: str) -> None:
    errors.setdefault(field, []).append(message)
