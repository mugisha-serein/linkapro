import pytest

from tasks.celery import (
    LOCAL_SETTINGS_MODULE,
    PRODUCTION_SETTINGS_ERROR,
    resolve_celery_settings_module,
)


def test_local_fallback_uses_development_settings_when_no_production_indicators():
    assert resolve_celery_settings_module({}) == LOCAL_SETTINGS_MODULE


def test_existing_django_settings_module_is_respected():
    assert (
        resolve_celery_settings_module({"DJANGO_SETTINGS_MODULE": "django_app.settings.test"})
        == "django_app.settings.test"
    )


@pytest.mark.parametrize(
    "environ",
    [
        {"RENDER": "true"},
        {"RENDER_EXTERNAL_HOSTNAME": "linkapro.onrender.com"},
        {"FASTAPI_ENV": "production"},
        {"DJANGO_ENV": "production"},
        {"ENVIRONMENT": "production"},
        {"DEBUG": "false"},
        {"DJANGO_DEBUG": "false"},
    ],
)
def test_production_like_env_without_django_settings_raises(environ):
    with pytest.raises(RuntimeError, match=PRODUCTION_SETTINGS_ERROR):
        resolve_celery_settings_module(environ)


def test_production_like_env_with_django_settings_passes():
    assert (
        resolve_celery_settings_module(
            {
                "RENDER": "true",
                "DJANGO_SETTINGS_MODULE": "django_app.settings.production",
            }
        )
        == "django_app.settings.production"
    )
