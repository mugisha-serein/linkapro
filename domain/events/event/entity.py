import uuid
from dataclasses import dataclass, field
from decimal import Decimal
from datetime import date, datetime
from typing import Optional, Union

from domain.events.event.errors import InvalidEventDetails
from domain.events.event.value_objects import EventType
from domain.events.shared.money import Money
from domain.shared.utils import utc_now

EventBudgetInput = Union[Money, Decimal, int, str, float]


@dataclass
class Event:
    """Main event entity owned by a planner."""

    id: uuid.UUID
    planner_id: uuid.UUID
    name: str
    event_type: EventType
    event_date: date
    venue: Optional[str] = None
    expected_guests: int = 0
    total_budget: Money = field(default_factory=lambda: Money(0))
    created_at: datetime = field(default_factory=utc_now)
    updated_at: datetime = field(default_factory=utc_now)

    def __post_init__(self) -> None:
        self.total_budget = self._coerce_money(self.total_budget)
        self._validate_name(self.name)
        self._validate_expected_guests(self.expected_guests)

    def update_details(
        self,
        name: Optional[str] = None,
        event_type: Optional[EventType] = None,
        event_date: Optional[date] = None,
        venue: Optional[str] = None,
        expected_guests: Optional[int] = None,
        total_budget: Optional[EventBudgetInput] = None,
    ) -> None:
        if name is not None:
            self._validate_name(name)
        if expected_guests is not None:
            self._validate_expected_guests(expected_guests)
        if total_budget is not None:
            total_budget = self._coerce_money(total_budget)

        if name is not None:
            self.name = name
        if event_type is not None:
            self.event_type = event_type
        if event_date is not None:
            self.event_date = event_date
        if venue is not None:
            self.venue = venue
        if expected_guests is not None:
            self.expected_guests = expected_guests
        if total_budget is not None:
            self.total_budget = total_budget
        self.updated_at = utc_now()

    @staticmethod
    def _coerce_money(amount: EventBudgetInput) -> Money:
        if isinstance(amount, float):
            return Money(str(amount))
        return Money(amount)

    @staticmethod
    def _validate_name(name: str) -> None:
        if not isinstance(name, str) or not name.strip():
            raise InvalidEventDetails("Event name must not be blank")

    @staticmethod
    def _validate_expected_guests(expected_guests: int) -> None:
        if expected_guests < 0:
            raise InvalidEventDetails("Expected guests must be greater than or equal to 0")
