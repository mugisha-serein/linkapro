"""Immutable value objects for the payment domain."""
from dataclasses import dataclass
from decimal import Decimal, ROUND_DOWN
from typing import Dict, Tuple


class DomainValidationError(ValueError):
    """Raised when a value object fails validation."""
    pass


class Currency:
    """ISO 4217 currency with decimal places and validation ranges."""
    
    _SUPPORTED: Dict[str, Dict] = {
        "RWF": {"decimals": 0, "min_minor": 100, "max_minor": 10_000_000},
        "USD": {"decimals": 2, "min_minor": 100, "max_minor": 1_000_000},
        "EUR": {"decimals": 2, "min_minor": 100, "max_minor": 1_000_000},
        "KES": {"decimals": 2, "min_minor": 100, "max_minor": 5_000_000},
        "GHS": {"decimals": 2, "min_minor": 100, "max_minor": 1_000_000},
        "NGN": {"decimals": 2, "min_minor": 100, "max_minor": 50_000_000},
    }

    def __init__(self, code: str):
        if code not in self._SUPPORTED:
            raise DomainValidationError(f"Unsupported currency: {code}")
        self.code = code
        self.decimals = self._SUPPORTED[code]["decimals"]
        self.min_minor = self._SUPPORTED[code]["min_minor"]
        self.max_minor = self._SUPPORTED[code]["max_minor"]

    def __eq__(self, other) -> bool:
        if not isinstance(other, Currency):
            return False
        return self.code == other.code

    def __hash__(self) -> int:
        return hash(self.code)

    def __str__(self) -> str:
        return self.code


@dataclass(frozen=True)
class Money:
    """Amount in minor units (integer). No floating point operations."""
    
    minor_units: int
    currency: Currency

    def __post_init__(self):
        if not isinstance(self.minor_units, int):
            raise DomainValidationError("minor_units must be an integer")
        if self.minor_units < self.currency.min_minor:
            raise DomainValidationError(
                f"Amount {self.minor_units} below minimum {self.currency.min_minor}"
            )
        if self.minor_units > self.currency.max_minor:
            raise DomainValidationError(
                f"Amount {self.minor_units} exceeds maximum {self.currency.max_minor}"
            )

    def to_decimal(self) -> Decimal:
        """Convert to decimal representation (for display only)."""
        return Decimal(self.minor_units) / Decimal(10 ** self.currency.decimals)

    @classmethod
    def from_decimal(cls, amount: Decimal, currency: Currency) -> "Money":
        """Create Money from decimal, rounding down to minor units."""
        factor = Decimal(10 ** currency.decimals)
        minor = int((amount * factor).to_integral_value(rounding=ROUND_DOWN))
        return cls(minor_units=minor, currency=currency)

    def __add__(self, other: "Money") -> "Money":
        if self.currency != other.currency:
            raise DomainValidationError("Cannot add different currencies")
        return Money(minor_units=self.minor_units + other.minor_units, currency=self.currency)

    def __sub__(self, other: "Money") -> "Money":
        if self.currency != other.currency:
            raise DomainValidationError("Cannot subtract different currencies")
        return Money(minor_units=self.minor_units - other.minor_units, currency=self.currency)
    
@dataclass(frozen=True)
class EncryptedField:
    """Carrier for encrypted field components. Pure domain value object."""
    ciphertext: bytes
    iv: bytes
    tag: bytes
    dek_encrypted: bytes

    def __post_init__(self):
        # Basic validation to ensure bytes
        for field_name in ["ciphertext", "iv", "tag", "dek_encrypted"]:
            value = getattr(self, field_name)
            if not isinstance(value, bytes):
                raise ValueError(f"{field_name} must be bytes")
        # GCM IV is typically 12 bytes
        if len(self.iv) != 12:
            raise ValueError("IV must be 12 bytes for GCM")
        if len(self.tag) != 16:
            raise ValueError("Authentication tag must be 16 bytes")