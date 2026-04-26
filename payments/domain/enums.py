from enum import Enum


class PaymentStatus(str, Enum):
    INITIATED = "initiated"
    PENDING = "pending"
    SUCCESS = "success"
    FAILED = "failed"
    CANCELLED = "cancelled"
    EXPIRED = "expired"
    REFUND_REQUESTED = "refund_requested"
    REFUNDED = "refunded"


class PaymentMethod(str, Enum):
    CARD = "card"
    MOBILE_MONEY = "mobile_money"
    BANK_TRANSFER = "bank_transfer"


class PaymentEnv(str, Enum):
    TEST = "test"
    LIVE = "live"