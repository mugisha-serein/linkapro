"""Session-domain errors."""
from domain.identity.shared import DomainError


class SessionError(DomainError):
    pass


class MalformedRefreshToken(SessionError):
    pass


class RefreshTokenReuseDetected(SessionError):
    pass


RefreshTokenReplayDetected = RefreshTokenReuseDetected


class TokenFamilyRevoked(SessionError):
    pass


class SessionRevoked(SessionError):
    pass


class SessionVersionMismatch(SessionError):
    pass
