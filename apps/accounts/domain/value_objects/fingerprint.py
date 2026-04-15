# Value Object - Immutable Business Concept
from __future__ import annotations

import hashlib
from dataclasses import dataclass
from typing import Dict, Any, Optional


@dataclass(frozen=True)
class Fingerprint:
    """
    Device fingerprint value object.

    Represents a device fingerprint in the business domain.
    Immutable and self-validating.
    """

    hash_value: str
    components: Dict[str, Any]

    def __post_init__(self):
        """Validate fingerprint and business rules."""
        self._validate_hash()
        self._validate_components()

    def _validate_hash(self) -> None:
        """Validate hash format and strength."""
        if not self.hash_value:
            raise ValueError("Fingerprint hash cannot be empty")

        # Must be at least 32 characters (MD5 length)
        if len(self.hash_value) < 32:
            raise ValueError("Fingerprint hash too short")

        # Must be hexadecimal
        try:
            int(self.hash_value, 16)
        except ValueError as e:
            raise ValueError(f"Invalid hash format: {self.hash_value}") from e

    def _validate_components(self) -> None:
        """Validate fingerprint components."""
        if not self.components:
            raise ValueError("Fingerprint components cannot be empty")

        required_components = ['user_agent', 'language', 'timezone']
        for component in required_components:
            if component not in self.components:
                raise ValueError(f"Missing required component: {component}")

    @classmethod
    def from_components(cls, components: Dict[str, Any]) -> Fingerprint:
        """Create fingerprint from device components."""
        # Create deterministic hash from components
        hash_input = cls._create_hash_input(components)
        hash_value = hashlib.sha256(hash_input.encode('utf-8')).hexdigest()

        return cls(hash_value=hash_value, components=components.copy())

    @staticmethod
    def _create_hash_input(components: Dict[str, Any]) -> str:
        """Create deterministic string from components for hashing."""
        # Sort keys for consistent hashing
        sorted_items = sorted(components.items())

        # Convert to string representation
        parts = []
        for key, value in sorted_items:
            if value is not None:
                parts.append(f"{key}:{str(value)}")

        return "|".join(parts)

    def matches(self, other: Fingerprint) -> bool:
        """Check if fingerprints match."""
        return self.hash_value == other.hash_value

    def similarity_score(self, other: Fingerprint) -> float:
        """Calculate similarity score between fingerprints (0.0 to 1.0)."""
        if self.matches(other):
            return 1.0

        # Count matching components
        matching_components = 0
        total_components = len(self.components)

        for key, value in self.components.items():
            if key in other.components and other.components[key] == value:
                matching_components += 1

        return matching_components / total_components if total_components > 0 else 0.0

    def is_similar(self, other: Fingerprint, threshold: float = 0.8) -> bool:
        """Check if fingerprints are similar above threshold."""
        return self.similarity_score(other) >= threshold

    def get_component(self, key: str) -> Any:
        """Get a specific component value."""
        return self.components.get(key)

    def has_component(self, key: str) -> bool:
        """Check if component exists."""
        return key in self.components

    @property
    def user_agent(self) -> Optional[str]:
        """Get user agent component."""
        return self.get_component('user_agent')

    @property
    def language(self) -> Optional[str]:
        """Get language component."""
        return self.get_component('language')

    @property
    def timezone(self) -> Optional[str]:
        """Get timezone component."""
        return self.get_component('timezone')

    @property
    def device_type(self) -> Optional[str]:
        """Get device type component."""
        return self.get_component('device_type')

    @property
    def browser(self) -> Optional[str]:
        """Get browser component."""
        return self.get_component('browser')

    @property
    def os(self) -> Optional[str]:
        """Get operating system component."""
        return self.get_component('os')