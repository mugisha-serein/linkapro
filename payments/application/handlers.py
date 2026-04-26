from datetime import timedelta
import uuid
from typing import Optional

from payments.domain.entities import Payment, AuditEvent
from payments.domain.enums import PaymentStatus, PaymentMethod, PaymentEnv
from payments.domain.step_up_policy import StepUpPolicy
from payments.domain.value_objects import Money, Currency
from payments.domain.policy import PaymentPolicy, PolicyResult
from payments.domain.events import FraudSignalEvent, PaymentCompleted, PaymentExpired

from payments.application.ports import (
    IPaymentRepository,
    IProviderGateway,
    IWebhookEventRepository,
    IAuditLogger,
    IRetryScheduler,
    IExpiryScanner,
    VerifiedTransactionDTO,
)
from payments.application.commands import (
    InitiatePaymentCommand,
    ProcessWebhookCommand,
    ExpireStalePaymentsCommand,
    RequestRefundCommand,
)
from payments.application.dtos import PaymentInitiationDTO, PaymentStatusDTO
from payments.application.exceptions import (
    PaymentNotFoundError,
    IdempotencyConflictError,
    PaymentNotAllowedError,
    ProviderGatewayError,
)
from payments.domain.velocity import VelocityContext, FraudContext, VelocityPolicy, FraudPatternPolicy
from payments.application.exceptions import VelocityLimitExceededError, FraudFlaggedError
from domain.shared.utils import utc_now

class PaymentCommandHandlers:
    def __init__(
        self,
        payment_repo: IPaymentRepository,
        provider_gateway: IProviderGateway,
        webhook_repo: IWebhookEventRepository,
        audit_logger: IAuditLogger,
        retry_scheduler: IRetryScheduler,
        expiry_scanner: IExpiryScanner,
        event_dispatcher,  # For domain events
    ):
        self.payment_repo = payment_repo
        self.provider_gateway = provider_gateway
        self.webhook_repo = webhook_repo
        self.audit_logger = audit_logger
        self.retry_scheduler = retry_scheduler
        self.expiry_scanner = expiry_scanner
        self.event_dispatcher = event_dispatcher

    def initiate_payment(self, cmd: InitiatePaymentCommand) -> PaymentInitiationDTO:
        # 1. Check idempotency
        existing = self.payment_repo.find_by_idempotency_key(cmd.idempotency_key)
        if existing:
            # Return existing if already initiated
            return PaymentInitiationDTO(
                reference=existing.reference,
                payment_link=f"{cmd.redirect_base_url}/pay/{existing.reference}",
                expires_at=existing.expires_at,
            )
        
        # 2. Velocity checks
        now = utc_now()
        velocity_ctx = self.payment_repo.get_velocity_context(cmd.user_id, now)
        velocity_result = VelocityPolicy.apply(str(cmd.user_id), velocity_ctx, now)
        if not velocity_result.allowed:
            # Log and raise generic error
            self.audit_logger.log(AuditEvent(id=uuid.uuid4(), payment_id=None, action="VELOCITY_BLOCK", actor=f"user:{cmd.user_id}", details={}))
            raise VelocityLimitExceededError("Transaction cannot be processed at this time.")
        if velocity_result.flag:
            # Emit a security event but do not block
            self.event_dispatcher.dispatch(...)
        
        # 3. Fraud pattern checks
        fraud_ctx = FraudContext(
            duplicate_context_ref=self.payment_repo.find_duplicate_context_ref(
                cmd.user_id, cmd.context_reference, now - timedelta(minutes=60)
            ),
            account_age_hours=velocity_ctx.account_age_hours,
            step_up_threshold_minor=StepUpPolicy.THRESHOLDS.get(cmd.amount.currency.code, 0),
        )
        fraud_result = FraudPatternPolicy.apply(cmd, fraud_ctx, now)
        if fraud_result.flagged:
            # Payment should be routed to human review – we set a special status or metadata
            # For now, we raise an exception that the view can convert to a "pending review" response
            raise FraudFlaggedError("Payment is under review.")
        
        # 4. Create domain entity
        payment = Payment(
            id=uuid.uuid4(),
            user_id=cmd.user_id,
            amount=cmd.amount,
            method=cmd.method,
            reference=self._generate_reference(),
            idempotency_key=cmd.idempotency_key,
            environment=cmd.environment,
            context_reference=cmd.context_reference,
            metadata=cmd.metadata or {},
        )

        # 5. Apply policy for initiation
        now = utc_now()
        policy_result = PaymentPolicy.apply(payment, "INITIATE", None, now)
        if not policy_result.allowed:
            raise PaymentNotAllowedError(policy_result.reason)

        # 6. Call provider to create payment link
        redirect_url = f"{cmd.redirect_base_url}/payment/return?ref={payment.reference}"
        try:
            payment_link, provider_ref = self.provider_gateway.create_payment_link(
                amount=payment.amount,
                currency=payment.amount.currency,
                reference=payment.reference,
                redirect_url=redirect_url,
                customer_email=cmd.customer_email,
                customer_name=cmd.customer_name,
                metadata=payment.metadata,
            )
        except Exception as e:
            raise ProviderGatewayError(f"Failed to create payment link: {str(e)}")

        payment.provider_reference = provider_ref
        payment.transition_to(PaymentStatus.PENDING, now)

        # 7. Persist
        self.payment_repo.save(payment)

        # 8. Audit log
        self.audit_logger.log(AuditEvent(
            id=uuid.uuid4(),
            payment_id=payment.id,
            action="INITIATE",
            actor=f"user:{cmd.user_id}",
            details={"idempotency_key": cmd.idempotency_key},
        ))

        return PaymentInitiationDTO(
            reference=payment.reference,
            payment_link=payment_link,
            expires_at=payment.expires_at,
        )

    def process_webhook(self, cmd: ProcessWebhookCommand) -> None:
        # Stage 1: Idempotency check (infrastructure already did? We'll re-check)
        if self.webhook_repo.exists(cmd.event_id):
            return  # Already processed

        # Store event as PROCESSING
        self.webhook_repo.save_event(cmd.event_id, "PROCESSING", cmd.payload)

        # Extract provider_reference from payload
        provider_ref = self._extract_provider_reference(cmd.payload)
        if not provider_ref:
            self.webhook_repo.save_event(cmd.event_id, "REJECTED_MISSING_REF", cmd.payload)
            return

        # Stage 3: Acquire lock
        lock_acquired = self.payment_repo.acquire_lock(provider_ref, ttl_seconds=30)
        if not lock_acquired:
            # Schedule retry
            self.retry_scheduler.schedule_webhook_retry(provider_ref, 30)
            self.webhook_repo.save_event(cmd.event_id, "LOCK_FAILED_RETRY", cmd.payload)
            return

        try:
            # Stage 4: Verify with provider API
            try:
                verification = self.provider_gateway.verify_transaction(provider_ref)
            except Exception as e:
                # Schedule retry with exponential backoff
                self.retry_scheduler.schedule_webhook_retry(provider_ref, 30)
                self.webhook_repo.save_event(cmd.event_id, "VERIFY_FAILED_RETRY", cmd.payload)
                return

            if not verification:
                # Provider couldn't verify; schedule retry
                self.retry_scheduler.schedule_webhook_retry(provider_ref, 30)
                self.webhook_repo.save_event(cmd.event_id, "VERIFY_FAILED_RETRY", cmd.payload)
                return

            # Stage 5: Fetch payment by provider_reference
            payment = self.payment_repo.find_by_provider_reference(provider_ref)
            if not payment:
                # Log unknown payment
                self.audit_logger.log(AuditEvent(
                    id=uuid.uuid4(),
                    payment_id=None,
                    action="UNKNOWN_PAYMENT",
                    actor="webhook",
                    details={"provider_reference": provider_ref, "event_id": cmd.event_id},
                ))
                self.webhook_repo.save_event(cmd.event_id, "REJECTED_UNKNOWN", cmd.payload)
                return

            # Stage 6: Apply policy
            context = type('Context', (), {
                'provider_verified': verification.status == 'successful',
                'provider_reference': verification.provider_reference,
                'provider_amount_minor': verification.amount_minor_units,
                'provider_currency': verification.currency_code,
                'environment': payment.environment.value if hasattr(payment.environment, 'value') else payment.environment,
            })
            policy_result = PaymentPolicy.apply(payment, "CONFIRM_SUCCESS", context, cmd.now)

            if policy_result.fraud_signal:
                # Emit fraud signal event, do NOT transition
                self.event_dispatcher.dispatch(FraudSignalEvent(
                    payment_id=payment.id,
                    provider_reference=provider_ref,
                    reason=policy_result.reason,
                    occurred_at=cmd.now,
                ))
                self.audit_logger.log(AuditEvent(
                    id=uuid.uuid4(),
                    payment_id=payment.id,
                    action="FRAUD_SIGNAL",
                    actor="webhook",
                    details={"reason": policy_result.reason, "event_id": cmd.event_id},
                ))
                self.webhook_repo.save_event(cmd.event_id, "FRAUD_DETECTED", cmd.payload)
            elif policy_result.allowed:
                # Transition to SUCCESS
                payment.transition_to(PaymentStatus.SUCCESS, cmd.now)
                self.payment_repo.save(payment)
                self.audit_logger.log(AuditEvent(
                    id=uuid.uuid4(),
                    payment_id=payment.id,
                    action="SUCCESS",
                    actor="webhook",
                    details={"event_id": cmd.event_id},
                ))
                self.event_dispatcher.dispatch(PaymentCompleted(
                    payment_id=payment.id,
                    user_id=payment.user_id,
                    amount_minor=payment.amount.minor_units,
                    currency=payment.amount.currency.code,
                    occurred_at=cmd.now,
                ))
                self.webhook_repo.save_event(cmd.event_id, "PROCESSED_SUCCESS", cmd.payload)
            else:
                # Not allowed, log but don't modify payment
                self.audit_logger.log(AuditEvent(
                    id=uuid.uuid4(),
                    payment_id=payment.id,
                    action="WEBHOOK_REJECTED",
                    actor="webhook",
                    details={"reason": policy_result.reason, "event_id": cmd.event_id},
                ))
                self.webhook_repo.save_event(cmd.event_id, "REJECTED_POLICY", cmd.payload)

        finally:
            self.payment_repo.release_lock(provider_ref)

    def expire_stale_payments(self, cmd: ExpireStalePaymentsCommand) -> int:
        """Expire payments that have passed their expiration time."""
        expired_payments = self.expiry_scanner.find_expired_pending(cmd.now)
        count = 0
        for payment in expired_payments:
            policy_result = PaymentPolicy.apply(payment, "EXPIRE", None, cmd.now)
            if policy_result.allowed:
                payment.transition_to(PaymentStatus.EXPIRED, cmd.now)
                self.payment_repo.save(payment)
                self.audit_logger.log(AuditEvent(
                    id=uuid.uuid4(),
                    payment_id=payment.id,
                    action="EXPIRE",
                    actor="system",
                    details={"expires_at": payment.expires_at.isoformat()},
                ))
                self.event_dispatcher.dispatch(PaymentExpired(
                    payment_id=payment.id,
                    occurred_at=cmd.now,
                ))
                count += 1
        return count

    def request_refund(self, cmd: RequestRefundCommand) -> None:
        now = cmd.now or utc_now()
        payment = self.payment_repo.find_by_reference(cmd.payment_reference)
        if not payment:
            raise PaymentNotFoundError(f"Payment {cmd.payment_reference} not found")

        if payment.status != PaymentStatus.SUCCESS:
            raise PaymentNotAllowedError("Refund only allowed for successful payments")

        # Check refund window (e.g., 30 days)
        refund_window_days = 30
        if (now - payment.created_at).days > refund_window_days:
            raise PaymentNotAllowedError("Refund window expired")

        payment.transition_to(PaymentStatus.REFUND_REQUESTED, now)
        self.payment_repo.save(payment)
        self.audit_logger.log(AuditEvent(
            id=uuid.uuid4(),
            payment_id=payment.id,
            action="REFUND_REQUESTED",
            actor=f"user:{cmd.requested_by}",
            details={"reason": cmd.reason},
        ))
        # Actual refund processing would be handled by a separate process

    def _generate_reference(self) -> str:
        return f"pay_{uuid.uuid4().hex[:12]}"

    def _extract_provider_reference(self, payload: dict) -> Optional[str]:
        # Flutterwave payload structure: data.tx_ref
        data = payload.get("data", {})
        return data.get("tx_ref")