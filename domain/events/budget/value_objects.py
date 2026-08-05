from enum import Enum


class BudgetCategory(str, Enum):
    VENUE = "venue"
    CATERING = "catering"
    PHOTOGRAPHY = "photography"
    DECOR = "decor"
    ENTERTAINMENT = "entertainment"
    TRANSPORTATION = "transportation"
    ATTIRE = "attire"
    OTHER = "other"

