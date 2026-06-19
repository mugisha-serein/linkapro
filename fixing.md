Fix LinkaPro Django startup crash caused by payments HMAC middleware Redis.from_url(settings.REDIS_URL).

Production traceback:
ValueError: Redis URL must specify one of the following schemes (redis://, rediss://, unix://)

Crash location:
payments/infrastructure/middleware.py
HmacRequestValidator.**init**
self.redis_client = Redis.from_url(settings.REDIS_URL)

Root cause:
The middleware creates a Redis client during Django middleware initialization. If REDIS_URL is missing, empty, malformed, quoted incorrectly, or rediss:// TLS params are not handled, Gunicorn cannot boot. Redis should not crash the whole Django app at startup, especially for non-payment routes.

Repository:

* Backend: linkapro

Tasks:

1. Inspect current files:

   * payments/infrastructure/middleware.py
   * django_app/settings/base.py
   * django_app/settings/production.py
   * tasks/celery.py
   * any Redis/cache helpers
   * deployment docs

2. Add centralized Redis configuration helper.
   Create a helper in a shared location, for example:

   * django_app/common/redis.py
     or
   * django_app/common/redis_config.py

   It should expose:

   * get_redis_url()
   * redis_uses_tls(url)
   * redis_ssl_options(url)
   * get_redis_client(optional=False)

   Behavior:

   * trim REDIS_URL
   * reject malformed URLs with clear ImproperlyConfigured in production checks
   * support redis:// and rediss://
   * for rediss:// use ssl_cert_reqs=CERT_REQUIRED
   * never log Redis password
   * do not use CERT_NONE in production

3. Fix settings.
   In base.py:

   * REDIS_URL = os.environ.get("REDIS_URL", "").strip()
   * configure Celery broker/result from REDIS_URL
   * if rediss://, set:
     CELERY_BROKER_USE_SSL = {"ssl_cert_reqs": ssl.CERT_REQUIRED}
     CELERY_REDIS_BACKEND_USE_SSL = {"ssl_cert_reqs": ssl.CERT_REQUIRED}

   In production.py:

   * do not override Celery broker/backend in a way that removes SSL config
   * validate REDIS_URL has valid scheme if Redis is required
   * fail with clear message:
     "REDIS_URL must start with redis:// or rediss://"

4. Fix payments HMAC middleware.
   Current issue:

   * Redis client is created in **init**
   * bad Redis kills entire Django app

   Change:

   * Do not create Redis client in **init**
   * Lazy initialize Redis only when HMAC validation needs Redis
   * For non-payment routes, middleware should pass through without touching Redis
   * For payment routes requiring HMAC, if Redis is unavailable/misconfigured:
     return controlled JSON 503 or 500 depending on security policy
     do not crash app startup
   * Webhook and JWT-authenticated dashboard payment requests should continue bypassing HMAC as current logic intends.

5. HMAC security rule.
   For HMAC-protected external payment routes:

   * Redis is required for nonce replay protection.
   * If Redis is unavailable, fail closed:
     return 503 {"error": "Payment request verification is temporarily unavailable"}
   * Do not allow HMAC-protected requests without nonce checking.
   * Do not fail open.

6. Replace direct Redis.from_url(settings.REDIS_URL).
   Use the centralized helper.
   Ensure rediss:// works with:

   * ssl_cert_reqs=CERT_REQUIRED
   * URL query param ssl_cert_reqs=CERT_REQUIRED if present
   * no insecure warning

7. Add safe startup diagnostics.
   Add a management command or Django check:
   python manage.py check_redis

   It should:

   * validate REDIS_URL scheme
   * mask password in output
   * attempt ping if requested
   * show whether TLS is enabled
   * never print secret

8. Add tests.
   Backend tests:

   * middleware **init** does not call Redis.from_url
   * non-payment route passes through even if REDIS_URL missing in local/test
   * HMAC route fails closed if Redis misconfigured
   * rediss:// URL builds Redis client with ssl_cert_reqs CERT_REQUIRED
   * production settings reject missing/malformed REDIS_URL with clear ImproperlyConfigured
   * Celery SSL config exists for rediss://

9. Render env documentation.
   Document exact value format:
   REDIS_URL=rediss://default:<PASSWORD>@relevant-eft-112987.upstash.io:6379?ssl_cert_reqs=CERT_REQUIRED

   Apply to:

   * Django web service
   * Celery worker
   * Celery beat

   Warn:

   * no quotes
   * no spaces
   * no line breaks
   * rotate credential if exposed

10. Validation commands:
    python manage.py check
    python manage.py shell -c "from django.conf import settings; print(settings.REDIS_URL[:8]); print(getattr(settings, 'CELERY_BROKER_USE_SSL', None))"
    pytest tests/django_app tests/payments -q

Start:
gunicorn django_app.wsgi:application --bind 0.0.0.0:$PORT

Rules:

* Do not let bad Redis config crash all non-payment pages at middleware import/startup.
* HMAC-protected payment routes must fail closed if Redis is unavailable.
* Use CERT_REQUIRED for rediss:// in production.
* Do not log Redis password.
* Do not use CERT_NONE in production.
* Keep forgot-password 202 behavior intact.

Return:

* Root cause
* Files changed
* New Redis helper location
* Middleware behavior before/after
* Render env value example
* Validation results
* Suggested branch and commit message
