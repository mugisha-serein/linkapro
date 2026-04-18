import uuid
import pytest
from unittest.mock import Mock
from datetime import date

from application.events.commands import CreateEventCommand
from application.events.handlers import EventCommandHandlers
from domain.events.entities import Event, EventType


@pytest.fixture
def mock_repos():
    return Mock(), Mock(), Mock(), Mock(), Mock(), Mock()


def test_create_event(mock_repos):
    event_repo, *others = mock_repos
    dispatcher = Mock()
    handlers = EventCommandHandlers(event_repo, *others, dispatcher)

    event_repo.save.side_effect = lambda e: e

    cmd = CreateEventCommand(
        planner_id=uuid.uuid4(),
        name="Test Event",
        event_type="corporate",
        event_date=date(2025, 5, 1),
    )
    result = handlers.create_event(cmd)

    assert result.name == "Test Event"
    event_repo.save.assert_called_once()
    dispatcher.dispatch.assert_called_once()