# Application Use Case - Logout User

from ...ports.repositories import SessionRepository
from ...ports.services import Clock
from apps.accounts.domain.services.session_policy import SessionPolicy

class LogoutUser:
    """
    Orchestrates the logout use case.
    """
    def __init__(self, session_repo: SessionRepository, clock: Clock):
        self.session_repo = session_repo
        self.clock = clock

    def execute(self, session_id: str, context: dict) -> bool:
        session = self.session_repo.get_by_id(session_id)
        if not session or not SessionPolicy.is_session_valid(session, {'now': self.clock.now()}):
            return False
        # ...existing code for session revocation, omitted for brevity...
        return True
