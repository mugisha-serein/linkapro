"""Pure domain policy for step‑up authentication."""
from dataclasses import dataclass
from typing import Optional
from datetime import datetime

from payments.domain.value_objects import Money


@dataclass(frozen=True)
class StepUpPolicyResult:
    required: bool
    reason: Optional[str] = None


class StepUpPolicy:
    """Determine if a payment requires step‑up authentication."""

    # Thresholds in minor units
    THRESHOLDS = {
        "RWF": 500_000,      # 500k RWF
        "USD": 50_000,       # $500 (stored in cents → 50000)
        "EUR": 50_000,       # €500
        "KES": 5_000_000,    # 50k KES (stored in cents? KES decimals=2, so 50000*100? Actually 50000 KES * 100 = 5,000,000 cents)
        "NGN": 20_000_000,   # 200k NGN (decimals=2 → 200000*100)
        "GHS": 50_000,       # 500 GHS (decimals=2 → 500*100)
    }

    @classmethod
    def is_step_up_required(cls, amount: Money, token_step_up: bool, now: datetime) -> StepUpPolicyResult:
        """Return True if step‑up is required for this amount."""
        threshold = cls.THRESHOLDS.get(amount.currency.code)
        if threshold is None:
            # Unsupported currency – default to requiring step‑up for safety
            return StepUpPolicyResult(required=True, reason="Unsupported currency")

        if amount.minor_units >= threshold and not token_step_up:
            return StepUpPolicyResult(required=True, reason=f"Amount exceeds threshold of {threshold} {amount.currency.code}")

        return StepUpPolicyResult(required=False)