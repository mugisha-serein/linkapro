import os
import subprocess
import sys
from pathlib import Path


PROJECT_ROOT = Path(__file__).resolve().parents[3]


def _production_env(**overrides):
    env = os.environ.copy()
    env.update(
        {
            "PYTHONPATH": str(PROJECT_ROOT),
            "DJANGO_SETTINGS_MODULE": "django_app.settings.production",
            "DJANGO_SECRET_KEY": "test-secret-key",
            "DATABASE_URL": "postgres://user:pass@localhost:5432/linkapro",
            "ALLOWED_HOSTS": "api.example.test",
            "CORS_ALLOWED_ORIGINS": "https://www.linkapro.rw",
            "REDIS_URL": "redis://localhost:6379/0",
            "SENDGRID_API_KEY": "sendgrid-key",
            "DEFAULT_FROM_EMAIL": "no-reply@linkapro.rw",
            "FRONTEND_URL": "https://www.linkapro.rw",
        }
    )
    for key, value in overrides.items():
        if value is None:
            env.pop(key, None)
        else:
            env[key] = value
    return env


def _import_settings(settings_module: str, env: dict[str, str]):
    return subprocess.run(
        [sys.executable, "-c", f"import {settings_module}; print('ok')"],
        cwd=PROJECT_ROOT,
        env=env,
        text=True,
        capture_output=True,
        check=False,
    )


def test_production_settings_raise_if_sendgrid_api_key_missing():
    result = _import_settings(
        "django_app.settings.production",
        _production_env(SENDGRID_API_KEY=None),
    )

    assert result.returncode != 0
    assert "SENDGRID_API_KEY must be set for production password reset emails." in result.stderr


def test_production_settings_raise_if_default_from_email_missing():
    result = _import_settings(
        "django_app.settings.production",
        _production_env(DEFAULT_FROM_EMAIL=None),
    )

    assert result.returncode != 0
    assert "DEFAULT_FROM_EMAIL must be set for production emails." in result.stderr


def test_production_settings_raise_if_frontend_url_missing():
    result = _import_settings(
        "django_app.settings.production",
        _production_env(FRONTEND_URL=None),
    )

    assert result.returncode != 0
    assert "FRONTEND_URL must be set for password reset links." in result.stderr


def test_production_settings_pass_with_required_email_env():
    result = _import_settings("django_app.settings.production", _production_env())

    assert result.returncode == 0, result.stderr
    assert "ok" in result.stdout


def test_local_and_test_settings_do_not_require_sendgrid():
    env = os.environ.copy()
    env.update(
        {
            "PYTHONPATH": str(PROJECT_ROOT),
            "DJANGO_SETTINGS_MODULE": "django_app.settings.development",
        }
    )
    env.pop("SENDGRID_API_KEY", None)
    env.pop("DEFAULT_FROM_EMAIL", None)
    result = subprocess.run(
        [
            sys.executable,
            "-c",
            "import django_app.settings.development; import django_app.settings.test; print('ok')",
        ],
        cwd=PROJECT_ROOT,
        env=env,
        text=True,
        capture_output=True,
        check=False,
    )

    assert result.returncode == 0, result.stderr
    assert "ok" in result.stdout
