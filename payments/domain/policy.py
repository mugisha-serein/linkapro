from dataclasses import dataclass
from datetime import datetime
from typing import Optional, Any

from .entities import Payment
from .enums import PaymentStatus, PaymentEnv


@dataclass(frozen=True)
class PolicyResult:
    allowed: bool
    reason: Optional[str] = None
    next_state: Optional[PaymentStatus] = None
    fraud_signal: bool = False


class PaymentPolicy:
    @staticmethod
    def apply(
        payment: Payment,
        action: str,
        context: Any,  # varies by action
        now: datetime,
    ) -> PolicyResult:
        if action == "INITIATE":
            return PaymentPolicy._evaluate_initiate(payment, now)
        elif action == "CONFIRM_SUCCESS":
            return PaymentPolicy._evaluate_confirm_success(payment, context, now)
        elif action == "EXPIRE":
            return PaymentPolicy._evaluate_expire(payment, now)
        else:
            return PolicyResult(allowed=False, reason=f"Unknown action: {action}")

    @staticmethod
    def _evaluate_initiate(payment: Payment, now: datetime) -> PolicyResult:
        if payment.status != PaymentStatus.INITIATED:
            return PolicyResult(allowed=False, reason="Payment already processed")
        if payment.is_expired(now):
            return PolicyResult(allowed=False, reason="Payment has expired")
        return PolicyResult(allowed=True, next_state=PaymentStatus.PENDING)

    @staticmethod
    def _evaluate_confirm_success(payment: Payment, context, now: datetime) -> PolicyResult:
        # Context must contain: provider_verified, provider_reference, provider_amount_minor,
        # provider_currency, environment
        fraud = False
        reasons = []

        if payment.status != PaymentStatus.PENDING:
            reasons.append(f"Payment not pending (current: {payment.status.value})")

        if not getattr(context, "provider_verified", False):
            reasons.append("Provider verification failed")

        if context.provider_reference != payment.provider_reference:
            reasons.append("Provider reference mismatch")
            fraud = True

        if context.provider_amount_minor != payment.amount.minor_units:
            reasons.append("Amount mismatch")
            fraud = True

        if context.provider_currency != payment.amount.currency.code:
            reasons.append("Currency mismatch")
            fraud = True

        if payment.is_expired(now):
            reasons.append("Payment has expired")

        if payment.environment != context.environment:
            reasons.append("Environment mismatch (test/live)")

        if reasons:
            return PolicyResult(
                allowed=False,
                reason="; ".join(reasons),
                fraud_signal=fraud,
            )

        return PolicyResult(allowed=True, next_state=PaymentStatus.SUCCESS)

    @staticmethod
    def _evaluate_expire(payment: Payment, now: datetime) -> PolicyResult:
        if payment.status not in (PaymentStatus.INITIATED, PaymentStatus.PENDING):
            return PolicyResult(allowed=False, reason="Payment not in expirable state")
        if not payment.is_expired(now):
            return PolicyResult(allowed=False, reason="Payment not yet expired")
        return PolicyResult(allowed=True, next_state=PaymentStatus.EXPIRED)


class ExpiryEvaluator:
    @staticmethod
    def is_expired(payment: Payment, now: datetime) -> bool:
        return payment.is_expired(now)

    @staticmethod
    def find_expired(now: datetime) -> bool:
        # This is a placeholder; actual query is in infrastructure
        pass