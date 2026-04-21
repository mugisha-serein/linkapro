import pytest
from tests.factories import create_event, create_user

@pytest.fixture
def event_factory():
    """Return a function that creates an Event with a planner."""
    def _create_event(**kwargs):
        if "planner" not in kwargs:
            kwargs["planner"] = create_user()
        return create_event(**kwargs)
    return _create_event