"""Read an identity account by ID."""

from dataclasses import dataclass
from typing import Optional
import uuid

from application.identity.dtos import UserDTO
from application.identity.shared.mappers import to_user_dto
from application.identity.shared.ports import IUserRepository


@dataclass(frozen=True)
class GetUserByIdQuery:
    user_id: uuid.UUID


class GetAccountQueryUseCase:
    def __init__(self, *, account_repository: IUserRepository) -> None:
        self.account_repository = account_repository

    def execute(self, query: GetUserByIdQuery) -> Optional[UserDTO]:
        user = self.account_repository.get_by_id(query.user_id)
        if not user:
            return None
        return to_user_dto(user)

    def get_user_by_id(self, query: GetUserByIdQuery) -> Optional[UserDTO]:
        return self.execute(query)


__all__ = ["GetAccountQueryUseCase", "GetUserByIdQuery"]
