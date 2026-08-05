from typing import List
import uuid

from domain.events.budget.interfaces import IBudgetLineRepository

from application.events.budget.dtos import BudgetLineDTO
from application.events.budget.mappers import to_budget_dto


class BudgetQueryHandlers:
    def __init__(self, budget_repo: IBudgetLineRepository):
        self.budget_repo = budget_repo

    def list_budget_lines(self, event_id: uuid.UUID) -> List[BudgetLineDTO]:
        lines = self.budget_repo.list_by_event(event_id)
        return [to_budget_dto(line) for line in lines]

