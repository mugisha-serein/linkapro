from __future__ import annotations

import os
from typing import Any

from django.core.exceptions import ImproperlyConfigured

from application.notifications.ports import IEmailSender


class ResendEmailSender(IEmailSender):
    def __init__(self) -> None:
        self._api_key = os.getenv("RESEND_API_KEY", "").strip()
        self._from_email = os.getenv("RESEND_FROM_EMAIL", "").strip()

        if self._is_production():
            missing = [
                name
                for name, value in (
                    ("RESEND_API_KEY", self._api_key),
                    ("RESEND_FROM_EMAIL", self._from_email),
                )
                if not value
            ]
            if missing:
                raise ImproperlyConfigured(f"{', '.join(missing)} must be set for production emails.")

    def send(self, to: str, template: str, context: dict) -> None:
        self._require_ready()

        import resend

        resend.api_key = self._api_key
        params: dict[str, Any] = {
            "from": self._from_email,
            "to": [to],
            "template": {
                "id": template,
                "variables": context,
            },
        }
        resend.Emails.send(params)

    def _require_ready(self) -> None:
        if not self._api_key:
            raise ImproperlyConfigured("RESEND_API_KEY must be set to send emails.")
        if not self._from_email:
            raise ImproperlyConfigured("RESEND_FROM_EMAIL must be set to send emails.")

    @staticmethod
    def _is_production() -> bool:
        settings_module = os.getenv("DJANGO_SETTINGS_MODULE", "").strip().lower()
        if settings_module.endswith(".production"):
            return True

        env_values = (
            os.getenv("APP_ENV", ""),
            os.getenv("DJANGO_ENV", ""),
            os.getenv("FASTAPI_ENV", ""),
            os.getenv("TOKEN_ENV", ""),
        )
        return any(value.strip().lower() == "production" for value in env_values)
