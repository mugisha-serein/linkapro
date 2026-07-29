"""Update identity account profile fields."""

from application.identity.account.update_profile_command import UpdateProfileCommand
from application.identity.dtos import UserDTO
from application.identity.errors import UserNotFoundError
from application.identity.shared.mappers import to_user_dto
from application.identity.shared.ports import AccountRepository


class UpdateAccountProfileUseCase:
    def __init__(self, *, account_repository: AccountRepository) -> None:
        self.account_repository = account_repository

    def execute(self, cmd: UpdateProfileCommand) -> UserDTO:
        user = self.account_repository.get_by_id(cmd.user_id)
        if not user:
            raise UserNotFoundError("User not found")

        user.update_profile(first_name=cmd.first_name, last_name=cmd.last_name)
        saved_user = self.account_repository.save(user)
        return to_user_dto(saved_user)


__all__ = ["UpdateAccountProfileUseCase"]
