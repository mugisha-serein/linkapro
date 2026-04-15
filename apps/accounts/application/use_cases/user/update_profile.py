# No Business Logic Here
from __future__ import annotations

from dataclasses import dataclass
from uuid import UUID

from django.db import transaction

from apps.accounts.application.dto.user_dto import UpdateProfileCommand, UpdateProfileResult
from apps.accounts.infrastructure.db.models import User
from apps.accounts.infrastructure.db.repositories import UserRepository


@dataclass(slots=True)
class UpdateProfileUseCase:
    user_repository: UserRepository

    def execute(self, command: UpdateProfileCommand) -> UpdateProfileResult:
        try:
            user_id = UUID(command.user_id)
        except ValueError:
            return UpdateProfileResult(
                success=False,
                user=None,
                failure_reason="INVALID_USER_ID",
                changes_made=None,
            )

        # Check if any fields are being updated
        if all(field is None for field in [command.email, command.role, command.is_active]):
            return UpdateProfileResult(
                success=False,
                user=None,
                failure_reason="NO_CHANGES_REQUESTED",
                changes_made=None,
            )

        user = self.user_repository.get_by_id(user_id)
        if user is None:
            return UpdateProfileResult(
                success=False,
                user=None,
                failure_reason="USER_NOT_FOUND",
                changes_made=None,
            )

        changes_made = []
        update_fields = ["updated_at"]

        with transaction.atomic():
            # Validate and update email
            if command.email is not None:
                normalized_email = command.email.strip().lower()
                if normalized_email != user.email:
                    # Check if email is already taken by another user
                    existing_user = self.user_repository.get_by_email(normalized_email)
                    if existing_user and existing_user.id != user.id:
                        return UpdateProfileResult(
                            success=False,
                            user=None,
                            failure_reason="EMAIL_ALREADY_EXISTS",
                            changes_made=None,
                        )
                    user.email = normalized_email
                    changes_made.append("email")
                    update_fields.append("email")

            # Validate and update role
            if command.role is not None:
                if command.role not in [User.Role.PLANNER, User.Role.VENDOR, User.Role.ADMIN]:
                    return UpdateProfileResult(
                        success=False,
                        user=None,
                        failure_reason="INVALID_ROLE",
                        changes_made=None,
                    )
                if command.role != user.role:
                    user.role = command.role
                    changes_made.append("role")
                    update_fields.append("role")

            # Update active status (this might require special permissions)
            if command.is_active is not None:
                if command.is_active != user.is_active:
                    user.is_active = command.is_active
                    changes_made.append("is_active")
                    update_fields.append("is_active")

            # Save the user if changes were made
            if changes_made:
                self.user_repository.save(user, update_fields=update_fields)

                # Refresh the user object to get updated data
                user.refresh_from_db()

        return UpdateProfileResult(
            success=True,
            user=user,
            failure_reason=None,
            changes_made=changes_made,
        )

    def __call__(self, command: UpdateProfileCommand) -> UpdateProfileResult:
        return self.execute(command)