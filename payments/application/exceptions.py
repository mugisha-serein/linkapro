class ApplicationError(Exception):
    """Base exception for application layer errors."""
    pass


class PaymentNotFoundError(ApplicationError):
    pass


class IdempotencyConflictError(ApplicationError):
    pass


class PaymentNotAllowedError(ApplicationError):
    def __init__(self, reason: str, fraud_signal: bool = False):
        self.reason = reason
        self.fraud_signal = fraud_signal
        super().__init__(reason)


class ProviderGatewayError(ApplicationError):
    pass


class WebhookProcessingError(ApplicationError):
    pass

class InfrastructureUnavailableError(ApplicationError):
    """Raised when a critical infrastructure service is unavailable."""
    pass

class KeyProviderError(ApplicationError):
    """Raised when key wrapping/unwrapping fails."""
    pass

class DecryptionError(ApplicationError):
    """Raised when field decryption fails."""
    pass

class VelocityLimitExceededError(ApplicationError):
    """Raised when velocity limits are exceeded (generic message returned to user)."""
    pass

class FraudFlaggedError(ApplicationError):
    """Payment flagged for manual review."""
    pass