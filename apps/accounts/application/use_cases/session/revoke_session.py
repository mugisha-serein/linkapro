# Application Use Case - Revoke Session

from ...ports.repositories import SessionRepository
from ...ports.services import Clock
from apps.accounts.domain.services.session_policy import SessionPolicy

class RevokeSession:
    """
    Orchestrates session revocation use case.
    """
    def __init__(self, session_repo: SessionRepository, clock: Clock):
        self.session_repo = session_repo
        self.clock = clock

    def execute(self, session_id: str, context: dict) -> bool:
        session = self.session_repo.get_by_id(session_id)
        if not session or not SessionPolicy.should_revoke_session(session, context):
            return False
        # ...existing code for session revocation, omitted for brevity...
        return True
