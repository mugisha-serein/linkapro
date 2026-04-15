# Application Layer Use Case Test - LoginUser
import pytest
from unittest.mock import Mock
from apps.accounts.application.use_cases.auth.login_user import LoginUser

class DummyUser:
    id = 'user-1'
    is_active = True
    locked_until = None

def test_login_success():
    user_repo = Mock(get_by_email=Mock(return_value=DummyUser()))
    session_repo = Mock()
    hasher = Mock(verify=Mock(return_value=True))
    clock = Mock(now=Mock(return_value=0))
    use_case = LoginUser(user_repo, session_repo, hasher, clock)
    result = use_case.execute('test@example.com', 'password', {})
    assert result.success
