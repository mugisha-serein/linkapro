from domain.events.budget.entity import BudgetLine

from application.events.budget.dtos import BudgetLineDTO


def to_budget_dto(b: BudgetLine) -> BudgetLineDTO:
    return BudgetLineDTO(
        id=b.id,
        event_id=b.event_id,
        category=b.category.value,
        description=b.description,
        estimated_cost=float(b.estimated_cost.amount),
        actual_cost=float(b.actual_cost.amount) if b.actual_cost is not None else None,
        notes=b.notes,
    )
