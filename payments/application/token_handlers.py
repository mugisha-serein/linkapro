import uuid
from datetime import datetime, timedelta
from typing import Optional, Tuple

from django.conf import settings
from django.core.cache import cache

from payments.application.ports import ITokenBlacklist
from payments.domain.step_up_policy import StepUpPolicy, StepUpPolicyResult


class TokenCommandHandlers:
    def __init__(self, blacklist: ITokenBlacklist):
        self.blacklist = blacklist

    def refresh_access_token(self, refresh_token: str) -> Tuple[str, str]:
        """Validate refresh token, rotate, and return new access + refresh pair."""
        from rest_framework_simplejwt.tokens import RefreshToken
        from rest_framework_simplejwt.exceptions import TokenError

        try:
            token = RefreshToken(refresh_token)
        except TokenError:
            raise ValueError("Invalid refresh token")

        jti = token.get("jti")
        family = token.get("family")

        # Check if token is blacklisted
        if self.blacklist.is_blacklisted(jti):
            # Token reuse = possible theft → blacklist whole family
            if family:
                self.blacklist.blacklist_family(family)
            raise ValueError("Token has been revoked")

        # Blacklist the used refresh token
        self.blacklist.blacklist(jti, ttl=int(token.lifetime.total_seconds()))

        # Generate new tokens with same claims (but new jti)
        new_refresh = RefreshToken()
        new_refresh["user_id"] = token["user_id"]
        new_refresh["scope"] = token.get("scope", "")
        new_refresh["env"] = token.get("env", "")
        new_refresh["step_up"] = token.get("step_up", False)
        new_refresh["family"] = family or str(uuid.uuid4())
        new_refresh["jti"] = str(uuid.uuid4())

        new_access = new_refresh.access_token
        new_access["user_id"] = token["user_id"]
        new_access["scope"] = token.get("scope", "")
        new_access["env"] = token.get("env", "")
        new_access["step_up"] = token.get("step_up", False)
        new_access["jti"] = str(uuid.uuid4())

        return str(new_access), str(new_refresh)

    def issue_step_up_token(self, user_id: str, original_token: dict) -> str:
        """Issue a short‑lived (5 min) access token with step_up=True."""
        from rest_framework_simplejwt.tokens import AccessToken

        token = AccessToken()
        token["user_id"] = user_id
        token["scope"] = original_token.get("scope", "")
        token["env"] = original_token.get("env", "")
        token["step_up"] = True
        token["jti"] = str(uuid.uuid4())
        token.set_exp(lifetime=timedelta(minutes=5))
        return str(token)