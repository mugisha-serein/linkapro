from __future__ import annotations

import os
import re
from pathlib import Path
from typing import Any

from django.core.exceptions import ImproperlyConfigured
from django.template import Context, Engine, TemplateDoesNotExist

from application.notifications.ports import IEmailSender


class ResendEmailSender(IEmailSender):
    _templates_dir = Path(__file__).resolve().parent / "templates"
    _template_engine = Engine(dirs=[str(_templates_dir)])

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
        rendered = self._render(template, context)

        import resend

        resend.api_key = self._api_key
        params: dict[str, Any] = {
            "from": self._from_email,
            "to": [to],
            "subject": rendered["subject"],
            "html": rendered["html"],
            "text": rendered["text"],
        }
        resend.Emails.send(params)

    def _render(self, template: str, context: dict) -> dict[str, str]:
        template_name = self._normalize_template_name(template)
        try:
            html_template = self._template_engine.get_template(f"{template_name}.html")
            text_template = self._template_engine.get_template(f"{template_name}.txt")
        except TemplateDoesNotExist as exc:
            raise ImproperlyConfigured(f"Email template {template!r} is not configured.") from exc

        rendered_context = Context(dict(context))
        html = html_template.render(rendered_context).strip()
        text = text_template.render(rendered_context).strip()
        subject, body = self._split_subject(text, template)
        return {"subject": subject, "html": html, "text": body}

    @staticmethod
    def _normalize_template_name(template: str) -> str:
        value = str(template or "").strip()
        if not value:
            raise ImproperlyConfigured("Email template name must be set.")
        if "/" in value or "\\" in value or ".." in value:
            raise ImproperlyConfigured("Email template name is invalid.")
        return re.sub(r"(?<!^)(?=[A-Z])", "_", value).replace("-", "_").lower()

    @staticmethod
    def _split_subject(text: str, template: str) -> tuple[str, str]:
        first_line, _, body = text.partition("\n")
        if not first_line.lower().startswith("subject:"):
            raise ImproperlyConfigured(f"Email template {template!r} must start with a Subject: line.")
        subject = first_line.partition(":")[2].strip()
        if not subject:
            raise ImproperlyConfigured(f"Email template {template!r} has an empty subject.")
        return subject, body.strip()

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
