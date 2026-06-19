Fix LinkaPro Celery Redis TLS configuration for rediss:// Redis URLs.

Problem:
Forgot password async email dispatch now works at HTTP level, but Celery dispatch is deferred with this error:

ValueError:
A rediss:// URL must have parameter ssl_cert_reqs and this must be set to CERT_REQUIRED, CERT_OPTIONAL, or CERT_NONE

Logs:

* forgot_password_email_queued
* Secure redis scheme specified (rediss) with no ssl options, defaulting to insecure SSL behaviour.
* forgot_password_email_dispatch_deferred

Root cause:
Production REDIS_URL uses rediss://, but Celery/redis-py/Kombu requires explicit SSL certificate options. Current Django settings use REDIS_URL directly for CELERY_BROKER_URL and CELERY_RESULT_BACKEND without CELERY_BROKER_USE_SSL / CELERY_REDIS_BACKEND_USE_SSL or ssl_cert_reqs query parameter.

Repository:

* Backend: linkapro

Files to inspect:

* django_app/settings/base.py
* django_app/settings/production.py
* tasks/celery.py
* tasks/email_tasks.py
* requirements files
* deployment docs/env docs

Goal:
Make Celery worker, beat, and Django web process work with secure rediss:// Redis in production without insecure SSL warnings or ValueError.

Tasks:

1. Add Redis TLS helper in settings.
   In django_app/settings/base.py, add:

   * import ssl
   * from urllib.parse import urlparse
   * helper `_redis_uses_tls(url)`
   * helper `_redis_ssl_options(url)`

   Required behavior:

   * if REDIS_URL starts with rediss://, set ssl_cert_reqs to ssl.CERT_REQUIRED
   * if REDIS_URL starts with redis://, no SSL options
   * never default production to CERT_NONE

2. Configure Celery SSL options.
   Ensure settings contain:

   REDIS_URL = os.environ.get("REDIS_URL")
   CELERY_BROKER_URL = REDIS_URL
   CELERY_RESULT_BACKEND = CELERY_BROKER_URL

   If REDIS_URL uses rediss://:
   CELERY_BROKER_USE_SSL = {"ssl_cert_reqs": ssl.CERT_REQUIRED}
   CELERY_REDIS_BACKEND_USE_SSL = {"ssl_cert_reqs": ssl.CERT_REQUIRED}

3. Remove duplicate unsafe overrides.
   production.py currently sets CELERY_BROKER_URL and CELERY_RESULT_BACKEND directly from REDIS_URL.
   Update production.py so it does not override or wipe out SSL settings from base.py.
   It may keep serializer/timezone settings, but must not lose SSL config.

4. Configure Django Redis cache TLS if needed.
   Current production cache uses:
   CACHES["default"]["LOCATION"] = REDIS_URL

   If Django RedisCache also warns/fails with rediss://, add proper OPTIONS for TLS.
   Keep this compatible with Django’s built-in RedisCache backend.

5. Production env guidance.
   Document that Render/Upstash REDIS_URL can also include:
   ?ssl_cert_reqs=CERT_REQUIRED

   Example:
   REDIS_URL=rediss://default:PASSWORD@HOST:PORT?ssl_cert_reqs=CERT_REQUIRED

   But code should also safely configure Celery SSL options.

6. Add validation command/check.
   Add or document a shell check:

   python manage.py shell -c "from django.conf import settings; print(settings.CELERY_BROKER_URL); print(getattr(settings, 'CELERY_BROKER_USE_SSL', None)); print(getattr(settings, 'CELERY_REDIS_BACKEND_USE_SSL', None))"

   Expected:

   * broker URL starts rediss://
   * CELERY_BROKER_USE_SSL contains ssl.CERT_REQUIRED
   * CELERY_REDIS_BACKEND_USE_SSL contains ssl.CERT_REQUIRED

7. Test Celery import/dispatch.
   Run:
   python -c "from tasks.celery import app; print(app.conf.broker_url); print(app.conf.broker_use_ssl); print(app.conf.redis_backend_use_ssl)"

   Then:
   celery -A tasks.celery inspect ping

   Or start worker:
   celery -A tasks.celery worker --loglevel=info

8. Verify forgot-password queue.
   Trigger forgot-password again.
   Expected logs:

   * forgot_password_email_queued
   * no rediss ssl warning
   * no forgot_password_email_dispatch_deferred ValueError
   * worker receives send_password_reset_email_task

9. Tests.
   Add settings tests if project has settings tests:

   * rediss:// REDIS_URL sets Celery SSL options to ssl.CERT_REQUIRED
   * redis:// REDIS_URL does not set SSL options
   * production settings do not remove SSL options

Rules:

* Use CERT_REQUIRED in production.
* Do not use CERT_NONE unless explicitly local/dev-only.
* Do not leave insecure rediss warning.
* Do not let production.py override base SSL config.
* Do not log Redis password.
* Forgot-password endpoint must still return 202 quickly.

Return:

* Root cause
* Files changed
* Exact settings added
* Render REDIS_URL example
* Validation results
* Suggested branch and commit message
