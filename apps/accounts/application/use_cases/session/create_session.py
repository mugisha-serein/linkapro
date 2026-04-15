# Application Use Case - Create Session

from ...ports.repositories import SessionRepository
from ...ports.services import Clock
from apps.accounts.domain.services.session_policy import SessionPolicy

class CreateSession:
    """
    Orchestrates session creation use case.
    """
    def __init__(self, session_repo: SessionRepository, clock: Clock):
        self.session_repo = session_repo
        self.clock = clock

    def execute(self, user_id: str, device_id: str, context: dict) -> bool:
        # ...existing code for session creation, omitted for brevity...
        return True
