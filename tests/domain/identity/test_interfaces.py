import inspect
from typing import Optional

from application.identity.shared.ports.account_repository import IUserRepository
from application.identity.shared.ports.totp_secret_repository import ITOTPSecretRepository
from domain.identity.mfa import TOTPSecret


class TestUserRepositoryInterface:
    def test_totp_secret_contract_uses_value_object(self):
        set_signature = inspect.signature(ITOTPSecretRepository.set_totp_secret)
        get_signature = inspect.signature(ITOTPSecretRepository.get_totp_secret)

        assert set_signature.parameters["secret"].annotation is TOTPSecret
        assert get_signature.return_annotation == Optional[TOTPSecret]
        assert hasattr(ITOTPSecretRepository, "clear_totp_secret")

    def test_repository_exposes_safer_deactivation_contract(self):
        assert hasattr(IUserRepository, "deactivate")
        delete_doc = IUserRepository.delete.__doc__ or ""
        assert "Dangerous" in delete_doc
        assert "normal account removal" in delete_doc
        assert "deactivate()" in delete_doc
        assert "scheduled deletion/anonymization workflow" in delete_doc
        assert not hasattr(IUserRepository, "anonymize")
