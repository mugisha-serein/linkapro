# No Business Logic Here
from __future__ import annotations

from typing import Protocol, Any

from apps.accounts.application.dto.auth_dto import CredentialVerificationResult, IssuedLoginTokens


class CredentialVerifier(Protocol):
    def verify(self, user: Any, password: str) -> CredentialVerificationResult:
        ...


class TokenIssuer(Protocol):
    def issue_login_tokens(self, user: Any, session_key: str) -> IssuedLoginTokens:
        ...

    def issue_refresh_tokens(self, user: Any, session: Any, family_id: str) -> IssuedLoginTokens:
        ...