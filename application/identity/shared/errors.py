"""Shared identity application errors."""


class IdentityApplicationError(Exception):
    """Base class for identity application-layer failures."""


class AccountNotFound(IdentityApplicationError):
    pass


class EmailAlreadyRegistered(IdentityApplicationError):
    pass


class AuthenticationFailed(IdentityApplicationError):
    pass


class EmailVerificationTokenInvalid(IdentityApplicationError):
    pass


class MfaEnrollmentNotFound(IdentityApplicationError):
    pass


class MfaEnrollmentExpired(IdentityApplicationError):
    pass


class OAuthIdentityConflict(IdentityApplicationError):
    pass


class OAuthAccountLinkingRequired(IdentityApplicationError):
    pass


class RefreshTokenInvalid(IdentityApplicationError):
    pass


class SessionNotActive(IdentityApplicationError):
    pass


__all__ = [
    "AccountNotFound",
    "AuthenticationFailed",
    "EmailAlreadyRegistered",
    "EmailVerificationTokenInvalid",
    "IdentityApplicationError",
    "MfaEnrollmentExpired",
    "MfaEnrollmentNotFound",
    "OAuthAccountLinkingRequired",
    "OAuthIdentityConflict",
    "RefreshTokenInvalid",
    "SessionNotActive",
]
