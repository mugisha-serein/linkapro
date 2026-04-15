# Value Object - Immutable Business Concept
from __future__ import annotations

from dataclasses import dataclass
from enum import Enum
from typing import Optional


class RiskLevel(Enum):
    """Risk level classifications."""
    SAFE = "SAFE"
    LOW = "LOW"
    MEDIUM = "MEDIUM"
    HIGH = "HIGH"
    CRITICAL = "CRITICAL"


@dataclass(frozen=True)
class RiskScore:
    """
    Risk score value object.

    Represents a security risk score in the business domain.
    Immutable and self-validating.
    """

    value: int
    level: RiskLevel
    factors: frozenset[str]  # Immutable set of risk factors
    confidence: float = 1.0

    def __post_init__(self):
        """Validate risk score and business rules."""
        self._validate_value()
        self._validate_confidence()
        self._validate_level_consistency()

    def _validate_value(self) -> None:
        """Validate score value range."""
        if not (0 <= self.value <= 100):
            raise ValueError(f"Risk score must be between 0-100: {self.value}")

    def _validate_confidence(self) -> None:
        """Validate confidence range."""
        if not (0.0 <= self.confidence <= 1.0):
            raise ValueError(f"Confidence must be between 0.0-1.0: {self.confidence}")

    def _validate_level_consistency(self) -> None:
        """Validate that level matches score range."""
        expected_level = self._calculate_level_from_score(self.value)
        if self.level != expected_level:
            raise ValueError(f"Level {self.level} inconsistent with score {self.value}")

    @staticmethod
    def _calculate_level_from_score(score: int) -> RiskLevel:
        """Calculate risk level from score value."""
        if score >= 80:
            return RiskLevel.CRITICAL
        elif score >= 60:
            return RiskLevel.HIGH
        elif score >= 40:
            return RiskLevel.MEDIUM
        elif score >= 20:
            return RiskLevel.LOW
        else:
            return RiskLevel.SAFE

    @classmethod
    def from_score(cls, score: int, factors: Optional[set[str]] = None, confidence: float = 1.0) -> RiskScore:
        """Create RiskScore from numeric score."""
        if not (0 <= score <= 100):
            raise ValueError(f"Invalid score: {score}")

        level = cls._calculate_level_from_score(score)
        factor_set = frozenset(factors or set())

        return cls(
            value=score,
            level=level,
            factors=factor_set,
            confidence=confidence
        )

    @classmethod
    def safe(cls, factors: Optional[set[str]] = None) -> RiskScore:
        """Create a safe risk score."""
        return cls.from_score(0, factors)

    @classmethod
    def low(cls, factors: Optional[set[str]] = None) -> RiskScore:
        """Create a low risk score."""
        return cls.from_score(25, factors)

    @classmethod
    def medium(cls, factors: Optional[set[str]] = None) -> RiskScore:
        """Create a medium risk score."""
        return cls.from_score(50, factors)

    @classmethod
    def high(cls, factors: Optional[set[str]] = None) -> RiskScore:
        """Create a high risk score."""
        return cls.from_score(75, factors)

    @classmethod
    def critical(cls, factors: Optional[set[str]] = None) -> RiskScore:
        """Create a critical risk score."""
        return cls.from_score(100, factors)

    def is_safe(self) -> bool:
        """Check if risk is safe."""
        return self.level == RiskLevel.SAFE

    def is_critical(self) -> bool:
        """Check if risk is critical."""
        return self.level == RiskLevel.CRITICAL

    def requires_attention(self) -> bool:
        """Check if risk requires attention."""
        return self.level in [RiskLevel.HIGH, RiskLevel.CRITICAL]

    def should_block(self) -> bool:
        """Business rule: determine if this risk should block access."""
        return self.level == RiskLevel.CRITICAL or (self.level == RiskLevel.HIGH and self.confidence > 0.8)

    def combine(self, other: RiskScore) -> RiskScore:
        """Combine this risk score with another."""
        # Weighted average of scores
        total_weight = self.confidence + other.confidence
        if total_weight == 0:
            combined_score = 0
            combined_confidence = 0.0
        else:
            combined_score = int((self.value * self.confidence + other.value * other.confidence) / total_weight)
            combined_confidence = min(1.0, (self.confidence + other.confidence) / 2)

        # Combine factors
        combined_factors = self.factors | other.factors

        return RiskScore.from_score(combined_score, set(combined_factors), combined_confidence)

    def add_factor(self, factor: str) -> RiskScore:
        """Add a risk factor."""
        new_factors = set(self.factors)
        new_factors.add(factor)
        return RiskScore.from_score(self.value, new_factors, self.confidence)

    def remove_factor(self, factor: str) -> RiskScore:
        """Remove a risk factor."""
        new_factors = set(self.factors)
        new_factors.discard(factor)
        return RiskScore.from_score(self.value, new_factors, self.confidence)

    def increase_score(self, amount: int) -> RiskScore:
        """Increase risk score by amount."""
        new_score = min(100, self.value + amount)
        return RiskScore.from_score(new_score, set(self.factors), self.confidence)

    def decrease_score(self, amount: int) -> RiskScore:
        """Decrease risk score by amount."""
        new_score = max(0, self.value - amount)
        return RiskScore.from_score(new_score, set(self.factors), self.confidence)

    def __str__(self) -> str:
        """String representation."""
        return f"RiskScore(value={self.value}, level={self.level.value}, confidence={self.confidence:.2f})"

    def __lt__(self, other: RiskScore) -> bool:
        """Less than comparison."""
        return self.value < other.value

    def __le__(self, other: RiskScore) -> bool:
        """Less than or equal comparison."""
        return self.value <= other.value

    def __gt__(self, other: RiskScore) -> bool:
        """Greater than comparison."""
        return self.value > other.value

    def __ge__(self, other: RiskScore) -> bool:
        """Greater than or equal comparison."""
        return self.value >= other.value