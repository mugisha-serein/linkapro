"""Budget command handlers for the event planning application layer."""

import uuid

from domain.events.budget.entity import BudgetLine
from domain.events.budget.interfaces import IBudgetLineRepository
from domain.events.budget.value_objects import BudgetCategory
from domain.events.domain_events import BudgetLineAdded
from domain.shared.utils import utc_now

from application.events.commands import AddBudgetLineCommand, UpdateBudgetLineCommand
from application.events.dtos import BudgetLineDTO


class BudgetCommandHandlers:
    def __init__(self, budget_repo: IBudgetLineRepository, event_dispatcher):
        self.budget_repo = budget_repo
        self.event_dispatcher = event_dispatcher

    def add_budget_line(self, cmd: AddBudgetLineCommand) -> BudgetLineDTO:
        line = BudgetLine(
            id=uuid.uuid4(),
            event_id=cmd.event_id,
            category=BudgetCategory(cmd.category),
            description=cmd.description,
            estimated_cost=cmd.estimated_cost,
            actual_cost=cmd.actual_cost,
            notes=cmd.notes,
        )
        saved = self.budget_repo.save(line)
        self.event_dispatcher.dispatch(
            BudgetLineAdded(budget_line_id=saved.id, event_id=saved.event_id, occurred_at=utc_now())
        )
        return self._to_budget_dto(saved)

    def update_budget_line(self, cmd: UpdateBudgetLineCommand) -> BudgetLineDTO:
        line = self.budget_repo.get_by_id(cmd.line_id)
        if not line:
            raise ValueError("Budget line not found")
        if cmd.estimated_cost is not None:
            line.update_estimate(cmd.estimated_cost)
        if cmd.actual_cost is not None:
            line.set_actual_cost(cmd.actual_cost)
        if cmd.notes is not None:
            line.notes = cmd.notes
        saved = self.budget_repo.save(line)
        return self._to_budget_dto(saved)

    @staticmethod
    def _to_budget_dto(b: BudgetLine) -> BudgetLineDTO:
        return BudgetLineDTO(
            id=b.id,
            event_id=b.event_id,
            category=b.category.value,
            description=b.description,
            estimated_cost=float(b.estimated_cost.amount),
            actual_cost=float(b.actual_cost.amount) if b.actual_cost is not None else None,
            notes=b.notes,
        )
