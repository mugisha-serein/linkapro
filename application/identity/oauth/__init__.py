"""OAuth identity application use cases."""

from .confirm_oauth_relink import ConfirmOAuthRelinkCommand, ConfirmOAuthRelinkUseCase
from .google_login_command import GoogleLoginCommand, OAuthLoginCommand, ProviderIdentity
from .google_login import GoogleLoginResult, GoogleLoginUseCase
from .request_oauth_relink import RequestOAuthRelinkCommand, RequestOAuthRelinkUseCase
from .revoke_oauth_token import RevokeOAuthTokenCommand, RevokeOAuthTokenUseCase
from .unlink_oauth_provider import UnlinkOAuthProviderCommand, UnlinkOAuthProviderUseCase

__all__ = [
    "ConfirmOAuthRelinkCommand",
    "ConfirmOAuthRelinkUseCase",
    "GoogleLoginCommand",
    "OAuthLoginCommand",
    "ProviderIdentity",
    "GoogleLoginResult",
    "GoogleLoginUseCase",
    "RequestOAuthRelinkCommand",
    "RequestOAuthRelinkUseCase",
    "RevokeOAuthTokenCommand",
    "RevokeOAuthTokenUseCase",
    "UnlinkOAuthProviderCommand",
    "UnlinkOAuthProviderUseCase",
]
