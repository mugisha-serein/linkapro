# No Business Logic Here
from __future__ import annotations

from dataclasses import dataclass
from uuid import UUID

from apps.accounts.application.dto.user_dto import GetProfileCommand, GetProfileResult
from apps.accounts.infrastructure.db.repositories import UserRepository


@dataclass(slots=True)
class GetProfileUseCase:
    user_repository: UserRepository

    def execute(self, command: GetProfileCommand) -> GetProfileResult:
        try:
            user_id = UUID(command.user_id)
        except ValueError:
            return GetProfileResult(
                success=False,
                user=None,
                failure_reason="INVALID_USER_ID",
            )

        user = self.user_repository.get_by_id(user_id)
        if user is None:
            return GetProfileResult(
                success=False,
                user=None,
                failure_reason="USER_NOT_FOUND",
            )

        return GetProfileResult(
            success=True,
            user=user,
            failure_reason=None,
        )

    def __call__(self, command: GetProfileCommand) -> GetProfileResult:
        return self.execute(command)