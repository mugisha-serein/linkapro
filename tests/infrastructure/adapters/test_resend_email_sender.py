from types import SimpleNamespace

import pytest
from django.core.exceptions import ImproperlyConfigured

from infrastructure.adapters.notifications.resend_email_sender import ResendEmailSender


def test_resend_email_sender_renders_template_and_calls_sdk(monkeypatch):
    sent = []

    class FakeEmails:
        @staticmethod
        def send(params):
            sent.append(params)

    fake_resend = SimpleNamespace(api_key=None, Emails=FakeEmails)
    monkeypatch.setitem(__import__("sys").modules, "resend", fake_resend)
    monkeypatch.setenv("RESEND_API_KEY", "test-api-key")
    monkeypatch.setenv("RESEND_FROM_EMAIL", "LinkaPro <no-reply@example.com>")
    monkeypatch.setenv("DJANGO_SETTINGS_MODULE", "django_app.settings.development")

    ResendEmailSender().send(
        to="planner@example.com",
        template="PaymentCompleted",
        context={
            "payment_reference": "pay_123",
            "amount": "15000",
            "currency": "RWF",
            "status": "success",
            "cta_url": "https://linkapro.test/payments/pay_123",
        },
    )

    assert fake_resend.api_key == "test-api-key"
    assert len(sent) == 1
    assert sent[0]["from"] == "LinkaPro <no-reply@example.com>"
    assert sent[0]["to"] == ["planner@example.com"]
    assert sent[0]["subject"] == "Your LinkaPro payment receipt"
    assert "pay_123" in sent[0]["html"]
    assert "pay_123" in sent[0]["text"]
    assert "template" not in sent[0]


def test_resend_email_sender_fails_fast_when_production_config_is_missing(monkeypatch):
    monkeypatch.delenv("RESEND_API_KEY", raising=False)
    monkeypatch.delenv("RESEND_FROM_EMAIL", raising=False)
    monkeypatch.setenv("DJANGO_SETTINGS_MODULE", "django_app.settings.production")

    with pytest.raises(ImproperlyConfigured, match="RESEND_API_KEY, RESEND_FROM_EMAIL"):
        ResendEmailSender()
