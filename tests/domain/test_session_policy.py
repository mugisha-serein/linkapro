# Domain Layer Unit Test - Session Policy
import pytest
from apps.accounts.domain.services.session_policy import SessionPolicy

class DummySession:
    state = 'ACTIVE'
    expires_at = 9999999999

def test_is_session_valid():
    session = DummySession()
    context = {'now': 0}
    assert SessionPolicy.is_session_valid(session, context)
