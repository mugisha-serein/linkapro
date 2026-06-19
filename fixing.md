Fix LinkaPro production email sending configuration for forgot password and reset-password emails.

Problem:
`django_app/settings/base.py` defines `SENDGRID_API_KEY`, but there is no confirmed `EMAIL_BACKEND`, `DEFAULT_FROM_EMAIL`, SendGrid backend wiring, SMTP host config, or production email validation. `ForgotPasswordView` uses Django `send_mail()`, so in production password reset emails may silently fail or use Django’s default local SMTP backend.

Current evidence:

* `ForgotPasswordView` calls `send_mail()` directly.
* `base.py` has `SENDGRID_API_KEY`, but no complete Django email backend config was found.
* In production, `send_mail()` catches exceptions, logs failure, and still returns 202 for security.
* User-facing response should stay generic, but the backend must actually send email and fail loudly in deployment/config checks when email is not configured.

Repository:

* Backend: linkapro

Goal:
Configure production email sending properly and make forgot-password email delivery production-safe, testable, and observable.

Backend tasks:

1. Inspect current email-related code/settings.
   Check:

   * django_app/settings/base.py
   * django_app/settings/production.py
   * django_app/identity/views.py
   * requirements files
   * existing SendGrid package usage
   * Render env documentation
   * tests for forgot password/reset password

2. Add production email backend configuration.
   Choose one stable implementation.

   Preferred simple option:
   Use Django SMTP backend with SendGrid SMTP:

   * EMAIL_BACKEND = "django.core.mail.backends.smtp.EmailBackend"
   * EMAIL_HOST = "smtp.sendgrid.net"
   * EMAIL_PORT = 587
   * EMAIL_USE_TLS = True
   * EMAIL_HOST_USER = "apikey"
   * EMAIL_HOST_PASSWORD = SENDGRID_API_KEY
   * DEFAULT_FROM_EMAIL from env
   * SERVER_EMAIL from env or DEFAULT_FROM_EMAIL

   Required env vars:

   * SENDGRID_API_KEY
   * DEFAULT_FROM_EMAIL
   * FRONTEND_URL

3. Add production config validation.
   In production settings, fail fast if required email env vars are missing:

   * SENDGRID_API_KEY
   * DEFAULT_FROM_EMAIL
   * FRONTEND_URL

   Use `ImproperlyConfigured` with clear messages:

   * "SENDGRID_API_KEY must be set for production password reset emails."
   * "DEFAULT_FROM_EMAIL must be set for production emails."
   * "FRONTEND_URL must be set for password reset links."

   Do not require SendGrid in local development/test.

4. Keep development/test safe.
   In development:

   * allow console email backend or locmem backend
   * do not require SendGrid API key
   * print reset email/link in console if appropriate

   In tests:

   * use locmem email backend
   * assert email sent without hitting external network

5. Refactor forgot-password email sending out of the view if appropriate.
   Create a small service, for example:

   * application/identity/password_reset_service.py
   * infrastructure/adapters/email_service.py
   * django_app/identity/email.py

   The service should:

   * generate reset token
   * build reset URL using FRONTEND_URL
   * send email with subject/body
   * log structured result
   * keep user-facing response generic

   Do not expose whether email exists to the user.

6. Improve email content.
   Send both plain text and optional HTML if project supports it.

   Plain text should include:

   * LinkaPro password reset request
   * reset link
   * expiration time, currently 1 hour
   * ignore message if user did not request it

   Example subject:
   "Reset your LinkaPro password"

7. Preserve security behavior.
   Forgot-password endpoint must always return 202 with generic message:
   {
   "detail": "If an account exists for that email, password reset instructions have been sent."
   }

   Do not reveal whether the email exists.
   Do not return 500 to the user just because email provider fails.
   But production logs must clearly show provider/config failure.

8. Add observability.
   Log structured information:

   * forgot_password_email_queued/sent/failed
   * target user id if found
   * email domain only or safely masked email
   * provider error safely
   * do not log full reset token
   * do not log full reset URL

9. Add management command for email smoke test.
   Add:
   python manage.py send_test_email --to [someone@example.com](mailto:someone@example.com)

   It should:

   * send a simple test email using configured backend
   * print success/failure clearly
   * never expose API key
   * useful for Render shell/job verification

10. Tests.
    Add/update tests:

* forgot-password existing active user sends one email
* forgot-password nonexistent email returns same 202 and sends no email
* forgot-password inactive user returns same 202 and sends no email
* email contains /auth/reset-password?token=
* email uses FRONTEND_URL
* reset token is not logged
* production settings raise ImproperlyConfigured if SENDGRID_API_KEY missing
* production settings raise ImproperlyConfigured if DEFAULT_FROM_EMAIL missing
* local/test settings do not require SendGrid

11. Documentation / Render env.
    Update README or deployment docs with required production env:
    SENDGRID_API_KEY=<sendgrid-api-key>
    DEFAULT_FROM_EMAIL=[no-reply@linkapro.rw](mailto:no-reply@linkapro.rw)
    FRONTEND_URL=https://www.linkapro.rw

Also include:
EMAIL_BACKEND=django.core.mail.backends.smtp.EmailBackend
EMAIL_HOST=smtp.sendgrid.net
EMAIL_PORT=587
EMAIL_USE_TLS=true
EMAIL_HOST_USER=apikey

If these are hardcoded from settings, document only the envs that must be set.

12. Validation commands.
    Run:
    python manage.py check
    python manage.py test django_app.identity
    or:
    pytest tests/django_app/identity -q

Also run the smoke command locally with console/locmem backend if possible.

Rules:

* Do not reveal account existence.
* Do not expose reset token in logs.
* Do not fail user-facing forgot-password request with 500 for email provider outage.
* Do fail production startup/config check if required email env vars are missing.
* Keep reset URL using FRONTEND_URL.
* Keep reset endpoint contract unchanged unless tests require standardization.
* No frontend changes yet unless route contract is broken.

Return:

* Root cause of current email weakness
* Files changed
* New env vars required
* Email backend selected
* Forgot-password response examples
* Test results
* Render setup instructions
* Suggested branch and commit message
