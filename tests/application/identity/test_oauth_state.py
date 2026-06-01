import time

import pytest
from django.conf import settings

from application.identity.oauth_state import build_oauth_state, parse_oauth_state


@pytest.mark.django_db
class TestOAuthState:
    def test_build_and_parse_valid_state(self):
        state = build_oauth_state("vendor")
        assert parse_oauth_state(state) == "vendor"

    def test_rejects_invalid_role_on_build(self):
        with pytest.raises(ValueError):
            build_oauth_state("admin")

    def test_rejects_tampered_state(self):
        state = build_oauth_state("planner")
        tampered = state[:-1] + ("x" if state[-1] != "x" else "y")
        assert parse_oauth_state(tampered) is None

    def test_rejects_expired_state(self, settings):
        settings.SECRET_KEY = "test-secret-key"
        state = build_oauth_state("planner")
        payload_b64, signature = state.rsplit(".", 1)
        assert parse_oauth_state(f"{payload_b64}.{signature}") == "planner"
