# Value Object - Immutable Business Concept
from __future__ import annotations

import ipaddress
from dataclasses import dataclass
from typing import Optional


@dataclass(frozen=True)
class IpAddress:
    """
    IP Address value object.

    Represents a validated IP address in the business domain.
    Immutable and self-validating.
    """

    value: str

    def __post_init__(self):
        """Validate IP address format and business rules."""
        self._validate_format()
        self._validate_business_rules()

    def _validate_format(self) -> None:
        """Validate IP address format."""
        try:
            ipaddress.ip_address(self.value)
        except ValueError as e:
            raise ValueError(f"Invalid IP address format: {self.value}") from e

    def _validate_business_rules(self) -> None:
        """Apply business-specific IP validation rules."""
        # Check for private/reserved addresses if needed
        ip_obj = ipaddress.ip_address(self.value)

        # Business rule: reject loopback addresses for external logins
        if ip_obj.is_loopback:
            raise ValueError("Loopback addresses not allowed")

        # Business rule: reject link-local addresses
        if ip_obj.is_link_local:
            raise ValueError("Link-local addresses not allowed")

    @property
    def is_private(self) -> bool:
        """Check if IP is in private range."""
        ip_obj = ipaddress.ip_address(self.value)
        return ip_obj.is_private

    @property
    def is_public(self) -> bool:
        """Check if IP is public."""
        return not self.is_private and not ipaddress.ip_address(self.value).is_loopback

    @property
    def version(self) -> int:
        """Get IP version (4 or 6)."""
        return ipaddress.ip_address(self.value).version

    def to_cidr(self, prefix_length: Optional[int] = None) -> str:
        """Convert to CIDR notation."""
        ip_obj = ipaddress.ip_address(self.value)
        if prefix_length is None:
            # Default prefix lengths
            prefix_length = 24 if self.version == 4 else 64

        network = ipaddress.ip_network(f"{self.value}/{prefix_length}", strict=False)
        return str(network)

    def is_in_range(self, cidr_range: str) -> bool:
        """Check if IP is within a CIDR range."""
        try:
            network = ipaddress.ip_network(cidr_range, strict=False)
            ip_obj = ipaddress.ip_address(self.value)
            return ip_obj in network
        except ValueError:
            return False

    @classmethod
    def from_string(cls, ip_str: str) -> IpAddress:
        """Create IpAddress from string (alias for constructor)."""
        return cls(ip_str)