"""Credential-oriented identity use cases."""

from .change_password import ChangePasswordUseCase
from .setup_password import SetupPasswordUseCase

__all__ = ["ChangePasswordUseCase", "SetupPasswordUseCase"]
