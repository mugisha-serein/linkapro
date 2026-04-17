# domain/__init__.py
# Public surface of the Domain Layer.

from domain.value_objects import (
    RoleType, SessionStatus, LoginOutcome, TokenStatus,
    UserId, SessionId, TokenId, TokenFamilyId,
    Email, HashedPassword, DeviceFingerprintValue,
    utc_now,
)
from domain.entities import (
    User, Role, UserRole, Session, DeviceFingerprint,
    RefreshToken, LoginActivity,
    MAX_FAILED_ATTEMPTS, LOCK_DURATION_MINUTES,
    DEFAULT_SESSION_TTL_MINUTES, DEFAULT_REFRESH_TTL_DAYS,
)
from domain.services import (
    AuthenticationService, AuthenticationResult, SessionValidationResult,
    SessionService, DeviceAnomalyResult,
    TokenService, RotationResult, ReuseHandlingResult,
)
from domain.exceptions import (
    DomainException,
    AccountInactiveError, AccountLockedError, AuthenticationNotAllowedError,
    InvalidCredentialsError,
    SessionInvalidError, SessionExpiredError, SessionRevokedError,
    SessionOwnershipError, DeviceBindingError,
    TokenReuseDetectedError, TokenExpiredError,
    TokenFamilyCompromisedError, TokenOrphanedError,
    RoleAlreadyAssignedError, RoleNotFoundError, UnauthorizedError,
    InvalidEmailError, InvalidPasswordError, InvalidFingerprintError,
)