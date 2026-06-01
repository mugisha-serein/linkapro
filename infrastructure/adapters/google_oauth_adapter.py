from urllib.parse import urlencode
import time

import requests
from django.conf import settings


class GoogleOAuthAdapterError(Exception):
    pass


class GoogleOAuthAdapter:
    AUTH_URL = "https://accounts.google.com/o/oauth2/v2/auth"
    TOKEN_URL = "https://oauth2.googleapis.com/token"
    TOKEN_INFO_URL = "https://oauth2.googleapis.com/tokeninfo"
    USERINFO_URL = "https://openidconnect.googleapis.com/v1/userinfo"
    VALID_ISSUERS = {"accounts.google.com", "https://accounts.google.com"}

    def build_auth_url(self, state: str | None = None) -> str:
        client_id = settings.GOOGLE_CLIENT_ID
        redirect_uri = settings.GOOGLE_REDIRECT_URI
        if not client_id or not redirect_uri:
            raise GoogleOAuthAdapterError("Google OAuth is not configured")
        if redirect_uri.rstrip("/") == self.AUTH_URL.rstrip("/"):
            raise GoogleOAuthAdapterError(
                "GOOGLE_REDIRECT_URI must be your backend callback URL, not Google's authorization URL"
            )
        self._enforce_https_in_production(redirect_uri, "GOOGLE_REDIRECT_URI")

        params = {
            "client_id": client_id,
            "redirect_uri": redirect_uri,
            "response_type": "code",
            "scope": "openid email profile",
            "access_type": "offline",
            "prompt": "consent",
        }
        if state:
            params["state"] = state
        return f"{self.AUTH_URL}?{urlencode(params)}"

    def exchange_code(self, code: str) -> dict:
        if not settings.GOOGLE_CLIENT_SECRET:
            raise GoogleOAuthAdapterError("Google OAuth is not configured")

        payload = {
            "code": code,
            "client_id": settings.GOOGLE_CLIENT_ID,
            "client_secret": settings.GOOGLE_CLIENT_SECRET,
            "redirect_uri": settings.GOOGLE_REDIRECT_URI,
            "grant_type": "authorization_code",
        }

        try:
            response = requests.post(self.TOKEN_URL, data=payload, timeout=10)
        except requests.RequestException as exc:
            raise GoogleOAuthAdapterError("Failed to reach Google token endpoint") from exc

        if not response.ok:
            raise GoogleOAuthAdapterError("Google token exchange failed")

        data = response.json()
        if "access_token" not in data:
            raise GoogleOAuthAdapterError("Google token response missing access_token")
        id_token = data.get("id_token")
        if not id_token:
            raise GoogleOAuthAdapterError("Google token response missing id_token")
        self._validate_id_token(id_token)
        return data

    def get_user_info(self, access_token: str) -> dict:
        headers = {"Authorization": f"Bearer {access_token}"}
        try:
            response = requests.get(self.USERINFO_URL, headers=headers, timeout=10)
        except requests.RequestException as exc:
            raise GoogleOAuthAdapterError("Failed to reach Google userinfo endpoint") from exc

        if not response.ok:
            raise GoogleOAuthAdapterError("Google userinfo request failed")

        data = response.json()
        google_id = data.get("sub")
        email = data.get("email")
        if not google_id or not email:
            raise GoogleOAuthAdapterError("Google userinfo missing required identity fields")
        email_verified = data.get("email_verified")
        if email_verified is False or str(email_verified).lower() == "false":
            raise GoogleOAuthAdapterError("Google email is not verified")

        return {
            "google_id": google_id,
            "email": email,
            "name": data.get("name", ""),
            "given_name": data.get("given_name", ""),
            "family_name": data.get("family_name", ""),
            "picture": data.get("picture", ""),
        }

    def _validate_id_token(self, id_token: str) -> None:
        try:
            response = requests.get(
                self.TOKEN_INFO_URL,
                params={"id_token": id_token},
                timeout=10,
            )
        except requests.RequestException as exc:
            raise GoogleOAuthAdapterError("Failed to validate Google id_token") from exc

        if not response.ok:
            raise GoogleOAuthAdapterError("Google id_token validation failed")

        claims = response.json()
        audience = claims.get("aud")
        issuer = claims.get("iss")
        if audience != settings.GOOGLE_CLIENT_ID:
            raise GoogleOAuthAdapterError("Google id_token audience mismatch")
        if issuer not in self.VALID_ISSUERS:
            raise GoogleOAuthAdapterError("Google id_token issuer mismatch")

        exp = claims.get("exp")
        if exp is not None:
            try:
                if int(exp) <= int(time.time()):
                    raise GoogleOAuthAdapterError("Google id_token is expired")
            except ValueError as exc:
                raise GoogleOAuthAdapterError("Google id_token exp claim is invalid") from exc

    @staticmethod
    def _enforce_https_in_production(url: str, field_name: str) -> None:
        if not settings.DEBUG and not url.lower().startswith("https://"):
            raise GoogleOAuthAdapterError(f"{field_name} must use HTTPS in production")
