"""Shared primitives for the event planning domain."""

from domain.events.shared.aggregate_root import AggregateRoot
from domain.events.shared.money import Money

__all__ = ["AggregateRoot", "Money"]
