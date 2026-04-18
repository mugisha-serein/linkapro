"""Queries for event planning read operations."""
from dataclasses import dataclass
import uuid


@dataclass(frozen=True)
class GetEventQuery:
    event_id: uuid.UUID


@dataclass(frozen=True)
class ListEventsByPlannerQuery:
    planner_id: uuid.UUID


@dataclass(frozen=True)
class GetChecklistQuery:
    checklist_id: uuid.UUID


@dataclass(frozen=True)
class ListChecklistsByEventQuery:
    event_id: uuid.UUID


@dataclass(frozen=True)
class GetBudgetSummaryQuery:
    event_id: uuid.UUID