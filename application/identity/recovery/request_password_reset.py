"""Request password reset instructions for an email address."""

from dataclasses import dataclass
from typing import Protocol


class PasswordResetRequestGateway(Protocol):
    def request_password_reset(self, email: str) -> bool:
        ...


@dataclass(frozen=True)
class RequestPasswordResetResult:
    queued: bool


class RequestPasswordResetUseCase:
    def __init__(self, *, gateway: PasswordResetRequestGateway) -> None:
        self.gateway = gateway

    def execute(self, *, email: str) -> RequestPasswordResetResult:
        queued = self.gateway.request_password_reset(email.strip().lower())
        return RequestPasswordResetResult(queued=queued)


__all__ = ["PasswordResetRequestGateway", "RequestPasswordResetResult", "RequestPasswordResetUseCase"]
