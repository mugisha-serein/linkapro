import logging
from copy import deepcopy
from contextlib import contextmanager, ExitStack
from unittest.mock import patch

import pytest
from django.conf import settings
from django.core.cache import cache
from django.test import override_settings
from django.urls import reverse
from rest_framework.test import APIClient

from django_app.identity.models import User
from django_app.identity.throttles import (
    ForgotPasswordEmailThrottle,
    ForgotPasswordIPThrottle,
    PasswordRecoveryThrottle,
    ResetPasswordIPThrottle,
    ResetPasswordTokenThrottle,
)

pytestmark = pytest.mark.django_db(transaction=True)


@pytest.fixture(autouse=True)
def clear_throttle_cache():
    cache.clear()
    yield
    cache.clear()


@pytest.fixture
def client():
    return APIClient()


@pytest.fixture
def active_user():
    return User.objects.create_user(
        email="limited@example.com",
        password="OldPass1!",
        first_name="Rate",
        last_name="Limited",
        role="planner",
    )


@pytest.fixture
def disable_email_dispatch(monkeypatch):
    monkeypatch.setattr("tasks.email_tasks.send_password_reset_email_task.delay", lambda *args, **kwargs: None)


@contextmanager
def recovery_rates(**overrides):
    config = deepcopy(settings.REST_FRAMEWORK)
    rates = {
        "forgot_password_ip": "100/min",
        "forgot_password_email": "100/hour",
        "reset_password_ip": "100/min",
        "reset_password_token": "100/hour",
    }
    rates.update(overrides)
    config["DEFAULT_THROTTLE_RATES"] = rates
    throttle_classes = {
        "forgot_password_ip": ForgotPasswordIPThrottle,
        "forgot_password_email": ForgotPasswordEmailThrottle,
        "reset_password_ip": ResetPasswordIPThrottle,
        "reset_password_token": ResetPasswordTokenThrottle,
    }
    with override_settings(REST_FRAMEWORK=config), ExitStack() as stack:
        for scope, throttle_class in throttle_classes.items():
            stack.enter_context(patch.object(throttle_class, "rate", rates[scope], create=True))
        yield


def test_forgot_password_existing_and_missing_are_same_under_limit(client, active_user, disable_email_dispatch):
    with recovery_rates():
        existing = client.post(reverse("forgot-password"), {"email": active_user.email}, format="json", REMOTE_ADDR="10.0.0.1")
        missing = client.post(reverse("forgot-password"), {"email": "missing@example.com"}, format="json", REMOTE_ADDR="10.0.0.2")

    assert existing.status_code == 202
    assert missing.status_code == 202
    assert existing.data == missing.data


def test_forgot_password_ip_limit_returns_safe_429(client):
    with recovery_rates(forgot_password_ip="1/min"):
        client.post(reverse("forgot-password"), {"email": "one@example.com"}, format="json", REMOTE_ADDR="10.0.0.3")
        response = client.post(reverse("forgot-password"), {"email": "two@example.com"}, format="json", REMOTE_ADDR="10.0.0.3")

    assert response.status_code == 429
    assert response.data == {
        "code": "password_recovery_rate_limited",
        "message": "Too many password reset attempts. Please try again later.",
    }
    assert int(response.headers["Retry-After"]) > 0


def test_forgot_password_email_hash_limit_returns_safe_429(client, active_user, disable_email_dispatch):
    with recovery_rates(forgot_password_email="1/hour"):
        client.post(reverse("forgot-password"), {"email": " LIMITED@EXAMPLE.COM "}, format="json", REMOTE_ADDR="10.0.0.4")
        response = client.post(reverse("forgot-password"), {"email": active_user.email}, format="json", REMOTE_ADDR="10.0.0.5")

    assert response.status_code == 429
    assert response.data["code"] == "password_recovery_rate_limited"
    assert "email" not in response.data["message"].lower()


def test_reset_password_ip_limit_returns_safe_429(client):
    with recovery_rates(reset_password_ip="1/min"):
        client.post(reverse("reset-password"), {"token": "invalid-one", "new_password": "ValidPass1!"}, format="json", REMOTE_ADDR="10.0.0.6")
        response = client.post(reverse("reset-password"), {"token": "invalid-two", "new_password": "ValidPass1!"}, format="json", REMOTE_ADDR="10.0.0.6")

    assert response.status_code == 429
    assert response.data == {
        "code": "password_reset_rate_limited",
        "message": "Too many reset attempts. Please wait before trying again.",
    }


def test_reset_password_token_hash_limit_returns_safe_429(client):
    with recovery_rates(reset_password_token="1/hour"):
        client.post(reverse("reset-password"), {"token": "same-secret-token", "new_password": "ValidPass1!"}, format="json", REMOTE_ADDR="10.0.0.7")
        response = client.post(reverse("reset-password"), {"token": "same-secret-token", "new_password": "ValidPass1!"}, format="json", REMOTE_ADDR="10.0.0.8")

    assert response.status_code == 429
    assert response.data["code"] == "password_reset_rate_limited"


def test_raw_email_and_token_are_not_used_in_cache_keys_or_logs(client, caplog):
    recording_cache = RecordingCache()
    original_cache = PasswordRecoveryThrottle.cache
    PasswordRecoveryThrottle.cache = recording_cache
    caplog.set_level(logging.INFO)
    try:
        with recovery_rates():
            client.post(reverse("forgot-password"), {"email": "raw@example.com"}, format="json", REMOTE_ADDR="10.0.0.9")
            client.post(reverse("reset-password"), {"token": "raw-reset-token", "new_password": "ValidPass1!"}, format="json", REMOTE_ADDR="10.0.0.10")
    finally:
        PasswordRecoveryThrottle.cache = original_cache

    joined_keys = " ".join(recording_cache.keys)
    assert "raw@example.com" not in joined_keys
    assert "raw-reset-token" not in joined_keys
    assert "raw@example.com" not in caplog.text
    assert "raw-reset-token" not in caplog.text


def test_rate_limiter_unavailable_fails_closed_and_logs(client, caplog):
    original_cache = PasswordRecoveryThrottle.cache
    PasswordRecoveryThrottle.cache = BrokenCache()
    caplog.set_level(logging.INFO, logger="django_app.identity.throttles")
    try:
        with recovery_rates():
            response = client.post(
                reverse("forgot-password"),
                {"email": "safe@example.com"},
                format="json",
                REMOTE_ADDR="10.0.0.11",
            )
    finally:
        PasswordRecoveryThrottle.cache = original_cache

    assert response.status_code == 429
    assert response.data["code"] == "password_recovery_rate_limited"
    assert "rate_limiter_unavailable" in caplog.text
    assert "safe@example.com" not in caplog.text


def test_scoped_rates_are_configurable_from_settings():
    with recovery_rates(forgot_password_email="7/hour", reset_password_token="9/hour"):
        assert settings.REST_FRAMEWORK["DEFAULT_THROTTLE_RATES"]["forgot_password_email"] == "7/hour"
        assert ForgotPasswordEmailThrottle().rate == "7/hour"
        assert ResetPasswordTokenThrottle().rate == "9/hour"


class RecordingCache:
    def __init__(self):
        self.data = {}
        self.keys = []

    def get(self, key, default=None):
        self.keys.append(key)
        return self.data.get(key, default)

    def set(self, key, value, timeout=None):
        self.keys.append(key)
        self.data[key] = value


class BrokenCache:
    def get(self, key, default=None):
        raise ConnectionError("redis unavailable")

    def set(self, key, value, timeout=None):
        raise ConnectionError("redis unavailable")
