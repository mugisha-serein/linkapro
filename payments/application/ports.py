"""Ports (interfaces) for the payment module. Infrastructure implements these."""
from abc import ABC, abstractmethod
from typing import Optional, List, Tuple
from uuid import UUID
from decimal import Decimal
from datetime import datetime

from payments.domain.entities import Payment, AuditEvent, PaymentStatus, PaymentMethod, PaymentEnv
from payments.domain.value_objects import Money, Currency
from payments.domain.velocity import VelocityContext
from payments.domain.webhook_crypto import DecryptionResult


class IPaymentRepository(ABC):
    """Repository for Payment aggregate."""

    @abstractmethod
    def save(self, payment: Payment) -> Payment:
        """Persist a new or updated payment. Returns the saved entity."""
        pass

    @abstractmethod
    def find_by_reference(self, reference: str) -> Optional[Payment]:
        """Find a payment by its internal reference (UUID-based string)."""
        pass

    @abstractmethod
    def find_by_provider_reference(self, provider_reference: str) -> Optional[Payment]:
        """Find a payment by the provider's transaction reference."""
        pass

    @abstractmethod
    def find_by_idempotency_key(self, idempotency_key: str) -> Optional[Payment]:
        """Find a payment by its idempotency key (used for duplicate initiation prevention)."""
        pass

    @abstractmethod
    def acquire_lock(self, provider_reference: str, ttl_seconds: int = 30) -> bool:
        """Acquire a distributed lock on the provider_reference. Returns True if acquired."""
        pass

    @abstractmethod
    def release_lock(self, provider_reference: str) -> None:
        """Release the distributed lock."""
        pass

    @abstractmethod
    def get_velocity_context(self, user_id: UUID, now: datetime) -> VelocityContext: ...
    
    @abstractmethod
    def find_duplicate_context_ref(self, user_id: UUID, context_ref: str, since: datetime) -> bool:
        pass 


class IProviderGateway(ABC):
    """Gateway to the payment provider (Flutterwave)."""

    @abstractmethod
    def create_payment_link(
        self,
        amount: Money,
        currency: Currency,
        reference: str,
        redirect_url: str,
        customer_email: str,
        customer_name: Optional[str] = None,
        metadata: Optional[dict] = None,
    ) -> Tuple[str, str]:  # returns (payment_link, provider_reference)
        """Create a hosted payment page link. Returns (url, provider_reference)."""
        pass

    @abstractmethod
    def verify_transaction(self, provider_reference: str) -> Optional['VerifiedTransactionDTO']:
        """Verify a transaction with the provider. Returns DTO with status and amount details."""
        pass


class IWebhookEventRepository(ABC):
    """Repository for incoming webhook events (idempotency)."""

    @abstractmethod
    def exists(self, event_id: str) -> bool:
        """Check if a webhook event with given ID has already been processed."""
        pass

    @abstractmethod
    def save_event(self, event_id: str, status: str, payload: dict) -> None:
        """Store a webhook event record with its processing status."""
        pass


class IAuditLogger(ABC):
    """Append-only audit log for compliance and security."""

    @abstractmethod
    def log(self, audit_event: AuditEvent) -> None:
        """Write an audit event. Must be append-only."""
        pass


class IRetryScheduler(ABC):
    """Schedule retries for failed webhook processing."""

    @abstractmethod
    def schedule_webhook_retry(self, provider_reference: str, delay_seconds: int) -> None:
        """Schedule a Celery task to retry webhook processing after delay."""
        pass


class IExpiryScanner(ABC):
    """Find payments that have expired but are still pending."""

    @abstractmethod
    def find_expired_pending(self, now: datetime) -> List[Payment]:
        """Return list of payments with status in (INITIATED, PENDING) and expires_at < now."""
        pass

class IKeyProvider(ABC):
    """Port for Key Management Service (Vault)."""

    @abstractmethod
    def wrap_dek(self, dek: bytes) -> bytes:
        """Encrypt a Data Encryption Key using the KEK.

        Args:
            dek: Plaintext 256-bit DEK (32 bytes).

        Returns:
            Encrypted DEK as bytes.

        Raises:
            InfrastructureUnavailableError: If Vault is unreachable.
        """
        pass

    @abstractmethod
    def unwrap_dek(self, encrypted_dek: bytes) -> bytes:
        """Decrypt an encrypted DEK using the KEK.

        Args:
            encrypted_dek: Wrapped DEK from Vault.

        Returns:
            Plaintext DEK (32 bytes).

        Raises:
            InfrastructureUnavailableError: If Vault is unreachable.
            KeyProviderError: If decryption fails.
        """
        pass

# DTO for verified transaction data (immutable)
class VerifiedTransactionDTO:
    def __init__(
        self,
        provider_reference: str,
        status: str,  # 'successful', 'failed', 'pending'
        amount_minor_units: int,
        currency_code: str,
        raw_response: dict,
    ):
        self.provider_reference = provider_reference
        self.status = status
        self.amount_minor_units = amount_minor_units
        self.currency_code = currency_code
        self.raw_response = raw_response
        
class IApiKeyRepository(ABC):
    @abstractmethod
    def find_by_key_id(self, key_id: str) -> Optional[dict]:
        """Return dict with keys: key_hash, scopes, user_id, is_active, expires_at."""
        pass

    @abstractmethod
    def mark_used(self, key_id: str) -> None:
        """Update last_used_at timestamp."""
        pass
    
class ITokenBlacklist(ABC):
    @abstractmethod
    def is_blacklisted(self, jti: str) -> bool: ...
    @abstractmethod
    def blacklist(self, jti: str, ttl: int) -> None: ...
    @abstractmethod
    def blacklist_family(self, family_id: str) -> None: ...
    
class IWebhookDecryptor(ABC):
    @abstractmethod
    def decrypt(self, base64_payload: str) -> DecryptionResult:
        """Decrypt a Base64-encoded 3DES-CBC payload."""
        pass