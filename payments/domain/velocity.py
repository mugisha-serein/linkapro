"""Pure domain services for velocity and fraud pattern detection."""
from dataclasses import dataclass, field
from datetime import datetime, timedelta
from typing import List, Optional

from payments.domain.value_objects import Money
from payments.domain.enums import PaymentMethod


# --- Context DTOs (data holders) ---

@dataclass(frozen=True)
class VelocityContext:
    payments_last_hour: int
    payments_last_day: int
    amount_last_day_minor: int           # sum of minor units across all payments
    failed_last_hour: int
    unique_vendors_last_hour: int
    account_age_hours: float             # hours since account creation


@dataclass(frozen=True)
class FraudContext:
    duplicate_context_ref: bool           # same context_reference used in last 60 min
    account_age_hours: float
    step_up_threshold_minor: int          # threshold for the currency


# --- Results ---

@dataclass(frozen=True)
class VelocityResult:
    allowed: bool
    reason: Optional[str] = None
    flag: bool = False                    # true if limit reached but only flag (not block)


@dataclass(frozen=True)
class FraudResult:
    flagged: bool
    reason: Optional[str] = None
    patterns: List[str] = field(default_factory=list)


# --- Policies ---

class VelocityPolicy:
    # Configurable limits (minor units where applicable)
    LIMITS = {
        "max_per_hour": 5,
        "max_per_day": 20,
        "max_amount_day_minor": 2_000_000,      # 2M RWF in minor units (RWF has 0 decimals, so 2,000,000)
        "max_failed_per_hour": 3,
        "max_unique_vendors_per_hour": 3,        # flag only
        "usd_cents_max_amount_day": 200_000,     # $2,000 in cents
    }

    @classmethod
    def apply(cls, user_id: str, context: VelocityContext, now: datetime) -> VelocityResult:
        # Check hourly limit
        if context.payments_last_hour >= cls.LIMITS["max_per_hour"]:
            return VelocityResult(allowed=False, reason="Hourly payment limit exceeded")
        # Check daily limit
        if context.payments_last_day >= cls.LIMITS["max_per_day"]:
            return VelocityResult(allowed=False, reason="Daily payment limit exceeded")
        # Check cumulative amount (currency-agnostic in minor units; we use a generic threshold)
        if context.amount_last_day_minor >= cls.LIMITS["max_amount_day_minor"]:
            return VelocityResult(allowed=False, reason="Daily amount limit exceeded")
        # Check failed attempts
        if context.failed_last_hour >= cls.LIMITS["max_failed_per_hour"]:
            return VelocityResult(allowed=False, reason="Too many failed payments")
        # Unique vendors – flag only, do not block
        if context.unique_vendors_last_hour >= cls.LIMITS["max_unique_vendors_per_hour"]:
            return VelocityResult(allowed=True, flag=True, reason="High number of unique vendors")
        return VelocityResult(allowed=True)


class FraudPatternPolicy:
    # Time windows
    DUPLICATE_WINDOW_MINUTES = 60
    NEW_ACCOUNT_HOURS = 24
    THRESHOLD_PROBING_PERCENT = 1.0   # 1% of step-up threshold

    @classmethod
    def apply(cls, payment, context: FraudContext, now: datetime) -> FraudResult:
        patterns = []
        if context.duplicate_context_ref:
            patterns.append("DUPLICATE_PURCHASE")
        if context.account_age_hours < cls.NEW_ACCOUNT_HOURS and payment.amount.minor_units >= context.step_up_threshold_minor:
            patterns.append("NEW_ACCOUNT_HIGH_VALUE")
        # Threshold probing: amount within 1% of step-up threshold
        threshold = context.step_up_threshold_minor
        margin = threshold * cls.THRESHOLD_PROBING_PERCENT / 100
        if threshold - margin <= payment.amount.minor_units <= threshold + margin:
            patterns.append("THRESHOLD_PROBING")
        if patterns:
            return FraudResult(flagged=True, reason="; ".join(patterns), patterns=patterns)
        return FraudResult(flagged=False)