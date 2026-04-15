# No Business Logic Here
from __future__ import annotations

from collections.abc import Iterable
from typing import Any

from django.conf import settings
from django.core.mail import EmailMessage, EmailMultiAlternatives


class EmailService:
    """
    Thin infrastructure adapter around Django's email backend.

    This service only forwards email payloads to the configured backend. It
    does not decide when or why emails should be sent.
    """

    def __init__(self, default_from_email: str | None = None) -> None:
        self.default_from_email = default_from_email or getattr(settings, "DEFAULT_FROM_EMAIL", None)

    def send_text_email(
        self,
        subject: str,
        body: str,
        recipient_list: Iterable[str],
        from_email: str | None = None,
        cc: Iterable[str] | None = None,
        bcc: Iterable[str] | None = None,
        reply_to: Iterable[str] | None = None,
        headers: dict[str, Any] | None = None,
        fail_silently: bool = False,
    ) -> int:
        message = EmailMessage(
            subject=subject,
            body=body,
            from_email=from_email or self.default_from_email,
            to=list(recipient_list),
            cc=list(cc) if cc is not None else None,
            bcc=list(bcc) if bcc is not None else None,
            reply_to=list(reply_to) if reply_to is not None else None,
            headers=headers,
        )
        return message.send(fail_silently=fail_silently)

    def send_html_email(
        self,
        subject: str,
        text_body: str,
        html_body: str,
        recipient_list: Iterable[str],
        from_email: str | None = None,
        cc: Iterable[str] | None = None,
        bcc: Iterable[str] | None = None,
        reply_to: Iterable[str] | None = None,
        headers: dict[str, Any] | None = None,
        fail_silently: bool = False,
    ) -> int:
        message = EmailMultiAlternatives(
            subject=subject,
            body=text_body,
            from_email=from_email or self.default_from_email,
            to=list(recipient_list),
            cc=list(cc) if cc is not None else None,
            bcc=list(bcc) if bcc is not None else None,
            reply_to=list(reply_to) if reply_to is not None else None,
            headers=headers,
        )
        message.attach_alternative(html_body, "text/html")
        if fail_silently:
            try:
                message.send(fail_silently=True)
            except Exception:
                return 0
            return 1
        return message.send(fail_silently=False)
