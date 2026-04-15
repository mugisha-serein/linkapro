# Domain Exceptions - Business Rule Violations

class DomainError(Exception):
    """Base class for all domain layer errors."""
    pass

class AuthenticationError(DomainError):
    """Raised when authentication fails due to business rules."""
    pass

class AuthorizationError(DomainError):
    """Raised when authorization fails due to business rules."""
    pass

class SessionError(DomainError):
    """Raised for session-related domain errors."""
    pass

class SecurityPolicyError(DomainError):
    """Raised for security policy violations or risk triggers."""
    pass

class ValidationError(DomainError):
    """Raised when a value object or entity fails validation."""
    pass
