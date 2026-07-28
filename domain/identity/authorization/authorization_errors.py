"""Authorization-domain errors."""
from domain.identity.shared import DomainError


class AuthorizationError(DomainError):
    """Base class for authorization failures."""


class RoleAssignmentDenied(AuthorizationError):
    """Raised when an actor is not allowed to assign a role."""


class RoleAssignmentRequiresActor(RoleAssignmentDenied):
    """Raised when a role transition lacks an authorizing actor."""


class RoleCannotBeSelfAssigned(RoleAssignmentDenied):
    """Raised when a user attempts to self-assign a privileged role."""
