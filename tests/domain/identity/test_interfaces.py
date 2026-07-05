import inspect
from typing import Optional

from domain.identity.interfaces import IUserRepository
from domain.identity.value_objects import TOTPSecret


class TestUserRepositoryInterface:
    def test_totp_secret_contract_uses_value_object(self):
        set_signature = inspect.signature(IUserRepository.set_totp_secret)
        get_signature = inspect.signature(IUserRepository.get_totp_secret)

        assert set_signature.parameters["secret"].annotation is TOTPSecret
        assert get_signature.return_annotation == Optional[TOTPSecret]
        assert hasattr(IUserRepository, "clear_totp_secret")

    def test_repository_exposes_safer_deactivation_contract(self):
        assert hasattr(IUserRepository, "deactivate")
        assert "Dangerous" in (IUserRepository.delete.__doc__ or "")
