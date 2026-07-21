from __future__ import annotations

from typing import Protocol


class IEmailSender(Protocol):
    def send(self, to: str, template: str, context: dict) -> None: ...
