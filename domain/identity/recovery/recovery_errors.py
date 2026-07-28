"""Recovery-domain errors."""
from domain.identity.shared import DomainError


class PasswordResetError(DomainError):
    pass


class InvalidPasswordResetToken(PasswordResetError):
    pass


class PasswordResetExpired(InvalidPasswordResetToken):
    pass


class PasswordResetAlreadyUsed(InvalidPasswordResetToken):
    pass


class PasswordResetUserInactive(PasswordResetError):
    pass
