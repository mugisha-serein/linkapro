class InvalidChecklistItem(ValueError):
    """Raised when a checklist item violates domain invariants."""


class ChecklistNotFound(ValueError):
    """Raised when a checklist or checklist item cannot be found."""
