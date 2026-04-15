# Application Use Case - Login User

from ...dto.auth_result import AuthResult
from ...ports.repositories import UserRepository, SessionRepository
from ...ports.services import PasswordHasher, Clock
from apps.accounts.domain.services.authentication_policy import AuthenticationPolicy

class LoginUser:
    """
    Orchestrates the login use case.
    Calls domain services and coordinates ports.
    """
    def __init__(self, user_repo: UserRepository, session_repo: SessionRepository, hasher: PasswordHasher, clock: Clock):
        self.user_repo = user_repo
        self.session_repo = session_repo
        self.hasher = hasher
        self.clock = clock

    def execute(self, email: str, password: str, context: dict) -> AuthResult:
        user = self.user_repo.get_by_email(email)
        if not user or not AuthenticationPolicy.is_login_allowed(user, {'now': self.clock.now()}):
            return AuthResult.failure("Login not allowed")
        if not self.hasher.verify(password, user):
            return AuthResult.failure("Invalid credentials")
        # ...existing code for session creation, omitted for brevity...
        return AuthResult.success(user_id=user.id)
