class NegativeBudgetAmount(ValueError):
    """Raised when a budget amount is below zero."""


class BudgetLineNotFound(ValueError):
    """Raised when a budget line cannot be found."""
