Fix LinkaPro forgot-password email failure observability while preserving secure generic 202 user response.

Problem:
Forgot-password currently returns generic 202 even when email sending fails. This is correct for security because it prevents account enumeration, but it is weak for operations because users think reset instructions were sent while the backend may have failed to queue or send the email.

Current desired behavior:

* User must always receive generic 202:
  {
  "detail": "If an account exists for that email, password reset instructions have been sent."
  }
* Backend must internally track, log, alert, and expose operational health when email queue/send fails.
* Do not reveal whether the submitted email belongs to an account.
* Do not log reset tokens or full reset URLs.

Repository:

* Backend: linkapro

Files to inspect:

* django_app/identity/views.py
* django_app/identity/serializers.py
* tasks/email_tasks.py
* django_app/settings/base.py
* django_app/settings/production.py
* tasks/celery.py
* governance/admin health endpoints if existing
* logging/structlog setup
* tests/django_app/identity
* tests/django_app/governance if existing

Goal:
Keep forgot-password secure for users, but make email delivery failures visible to backend/admin operations.

Backend tasks:

1. Preserve secure response contract.
   Forgot-password endpoint must always return 202 with the same generic message for:

   * existing active email
   * nonexistent email
   * inactive user
   * Celery dispatch failure
   * email provider failure

   Do not expose account existence or provider status to the user.

2. Add structured email dispatch logging.
   When forgot-password receives a valid email:

   * log forgot_password_requested with safe metadata
   * if user exists, log forgot_password_email_dispatch_attempted
   * if Celery task dispatch succeeds, log forgot_password_email_queued
   * if dispatch fails, log forgot_password_email_dispatch_failed or forgot_password_email_dispatch_deferred

   Safe metadata:

   * user_id if account exists
   * email_domain only
   * masked_email if needed, for example m***@gmail.com
   * request_id/correlation_id if available
   * do not log token
   * do not log full reset URL

3. Add task-level delivery logging.
   In password reset email task:

   * log password_reset_email_send_started
   * log password_reset_email_sent on success
   * log password_reset_email_failed on failure
   * include task_id, user_id, provider, attempt count
   * mask email
   * do not log reset token
   * do not log full reset URL

4. Add durable delivery status if appropriate.
   Add a lightweight model if there is no existing job/audit table:

   PasswordResetEmailDelivery

   * id UUID
   * user FK nullable or user_id UUID
   * email_hash
   * email_domain
   * status: queued, sent, failed, deferred
   * failure_reason safe text
   * attempts integer
   * provider: sendgrid_smtp or configured backend
   * queued_at
   * sent_at nullable
   * failed_at nullable
   * created_at/updated_at

   Do not store reset token.
   Do not store raw email if avoidable. If raw email is required for sending, store only in task payload or use user lookup by id.

5. Add retry behavior.
   The email task should retry transient provider/network failures with backoff.
   Example:

   * max_retries = 3 or 5
   * exponential backoff
   * final failure marks delivery status as failed
   * no user-facing 500

6. Add admin/ops health endpoint.
   If governance/admin health endpoints exist, extend them.
   Otherwise add a small admin-only endpoint:

   GET /api/django/governance/admin/health/email/

   It should return:
   {
   "email_backend_configured": true,
   "default_from_email_configured": true,
   "frontend_url_configured": true,
   "recent_password_reset_email_failures": 0,
   "recent_password_reset_email_deferred": 0,
   "last_success_at": "...",
   "last_failure_at": null,
   "status": "healthy|degraded|unhealthy"
   }

   Access:

   * admin only
   * authenticated
   * do not expose tokens or user emails

7. Add management command for smoke test.
   Add:
   python manage.py send_test_email --to [someone@example.com](mailto:someone@example.com)

   Behavior:

   * sends test email using configured backend
   * prints success/failure
   * masks provider secrets
   * useful for Render deploy verification

8. Add alert-friendly logging.
   Ensure failures are logged at warning/error level with stable event names:

   * password_reset_email_dispatch_failed
   * password_reset_email_failed
   * email_backend_misconfigured
   * email_health_unhealthy

   These names should be easy to search in Render logs.

9. Add config validation.
   In production settings, fail startup if core email config is missing:

   * SENDGRID_API_KEY
   * DEFAULT_FROM_EMAIL
   * FRONTEND_URL

   But runtime provider failures should not break forgot-password response.

10. Tests.
    Add/update tests:

* forgot-password existing user returns 202 and queues email
* nonexistent email returns same 202 and queues nothing
* Celery dispatch failure returns same 202 and logs/deferred status
* email task success marks delivery sent
* email task failure marks delivery failed after retries
* logs do not contain reset token
* logs do not contain full reset URL
* admin health endpoint shows degraded/unhealthy when recent failures exist
* admin health endpoint is admin-only
* production settings require email env vars

11. Validation commands.
    Run:
    python manage.py makemigrations
    python manage.py check
    pytest tests/django_app/identity tests/django_app/governance -q

Smoke test:
python manage.py send_test_email --to [your-email@example.com](mailto:your-email@example.com)

Rules:

* User-facing forgot-password response stays generic 202.
* Never reveal if email exists.
* Never log reset token.
* Never log full reset URL.
* Do not make the HTTP request wait for provider delivery.
* Backend must expose operational visibility for email failures.
* Admin/ops can see health, users cannot.

Return:

* Root cause of current operational blind spot
* Files changed
* Migration name if model added
* New log event names
* New health endpoint response example
* Smoke test command
* Validation results
* Suggested branch and commit message
