Fix LinkaPro forgot-password timeout by moving password reset email sending out of the request path and returning 202 immediately.

Problem:
Forgot password request is failing with frontend message:
"An unexpected error occurred"

Browser/DevTools shows:
POST https://linkapro-django.onrender.com/api/django/identity/forgot-password/
net::ERR_ABORTED after exactly 10 seconds.

Root cause:
Frontend Axios client has `timeout: 10000`, so it aborts the request after 10 seconds. Backend forgot-password endpoint currently calls Django `send_mail()` synchronously inside the request. If SMTP/SendGrid/Render is slow, the backend does not respond before the frontend timeout. Then frontend shows the generic normalized error.

Repositories:

* Backend: linkapro
* Frontend: linkapro-frontend

Current backend:

* django_app/identity/views.py
* ForgotPasswordView generates reset token and calls `send_mail()` directly.
* It returns 202 only after email sending finishes or fails.

Goal:
Forgot-password endpoint must always respond quickly with generic 202, while email delivery happens asynchronously or deferred. User must not wait for SendGrid/SMTP. Frontend should show correct messages and not generic “unexpected” for timeout/network cases.

Backend tasks:

1. Inspect current forgot-password implementation.
   Files:

   * django_app/identity/views.py
   * django_app/identity/serializers.py
   * infrastructure/adapters/jwt_token_service.py
   * tasks/celery.py
   * any existing email/task modules
   * django_app/settings/base.py
   * django_app/settings/production.py

2. Move email sending out of ForgotPasswordView.
   ForgotPasswordView should:

   * validate email
   * normalize email
   * find active user if exists
   * if user exists, create password reset token
   * enqueue background task to send reset email
   * if enqueue fails, save a deferred email job or log structured failure
   * return 202 immediately either way

   The user-facing response must remain enumeration-safe:
   {
   "detail": "If an account exists for that email, password reset instructions have been sent."
   }

3. Add Celery task.
   Create task, for example:

   * tasks/email_tasks.py
     or appropriate existing tasks module.

   Task:
   send_password_reset_email_task(user_id, token)

   It must:

   * fetch active user by id
   * build reset URL from FRONTEND_URL:
     {FRONTEND_URL}/auth/reset-password?token={token}
   * send email using configured Django email backend
   * retry transient SMTP/SendGrid failures with backoff
   * log success/failure safely
   * never log full token or full reset URL
   * be idempotent enough for retries

4. Register Celery task.
   Ensure task is imported/discovered by Celery worker.
   Inspect:

   * tasks/celery.py
   * tasks/**init**.py
   * app.autodiscover_tasks or explicit imports

5. Deferred fallback if Celery/Redis is down.
   If calling `.delay()` fails:

   * Do not block request.
   * Do not call send_mail synchronously.
   * Return 202 anyway.
   * Log structured error:
     forgot_password_email_dispatch_deferred
   * Optionally create a durable `PendingEmail`/`PasswordResetEmailJob` model or management command if the project already has a deferred job pattern.
   * If no deferred model is added in this phase, at minimum ensure no request timeout and clear logs show dispatch failure.

6. Optional durable deferred email job.
   Recommended for production:
   Add model:
   PasswordResetEmailJob

   * id
   * user FK
   * token_hash or encrypted token if storing token is unavoidable
   * email
   * status: pending, sent, failed
   * attempts
   * last_error
   * created_at
   * updated_at
   * next_attempt_at

   But avoid storing raw token if possible. Prefer enqueue-only if Celery is reliable.

7. Email backend config must exist.
   Ensure production settings configure email:

   * EMAIL_BACKEND = "django.core.mail.backends.smtp.EmailBackend"
   * EMAIL_HOST = "smtp.sendgrid.net"
   * EMAIL_PORT = 587
   * EMAIL_USE_TLS = True
   * EMAIL_HOST_USER = "apikey"
   * EMAIL_HOST_PASSWORD = SENDGRID_API_KEY
   * DEFAULT_FROM_EMAIL from env
   * SERVER_EMAIL from env or DEFAULT_FROM_EMAIL

   Production must fail fast if missing:

   * SENDGRID_API_KEY
   * DEFAULT_FROM_EMAIL
   * FRONTEND_URL

8. Keep security behavior.

   * Do not reveal whether email exists.
   * Do not return 500 to user if email provider is slow/down.
   * Do not log reset token.
   * Do not log full reset URL.
   * Do not include user email in unsafe logs; mask it or log domain/user id.

9. Frontend tasks.
   Inspect:

   * src/services/apiClient.ts
   * src/services/authService.ts
   * src/app/auth/forgot-password/page.tsx
   * src/lib/apiErrors.ts

   Fix user-facing timeout/network message:

   * If request times out or is aborted, show:
     "We couldn’t send reset instructions right now. Please try again."
   * Do not show "An unexpected error occurred."
   * Keep success state on 202.
   * Do not reveal whether account exists.
   * Keep frontend timeout if desired, but backend should respond fast.
   * Optionally allow a slightly longer timeout for auth email endpoints, but do not rely on this as the main fix.

10. Add response timing test.
    Backend test should prove ForgotPasswordView does not call SMTP synchronously:

* mock Celery task delay
* call forgot-password
* assert 202 returned
* assert task enqueued for existing user
* assert nonexistent email returns same 202 and does not enqueue
* assert `.delay()` failure still returns 202 quickly

11. Add task tests.

* task sends email for active user
* task skips inactive/missing user safely
* email contains /auth/reset-password?token=
* token not logged

12. Add frontend/manual tests.

* forgot password success 202 shows check email screen
* backend timeout/network error shows retry message, not unexpected
* nonexistent email still shows same success state if backend returns 202
* no account existence leak

13. Validation commands.
    Backend:
    python manage.py check
    pytest tests/django_app/identity -q

Celery import check:
python -c "from tasks.celery import app; print(app.tasks.keys())"

Frontend:
npm run lint
npm run build

Render production env:
SENDGRID_API_KEY=<sendgrid-api-key>
DEFAULT_FROM_EMAIL=[no-reply@linkapro.rw](mailto:no-reply@linkapro.rw)
FRONTEND_URL=https://www.linkapro.rw
REDIS_URL=<upstash-redis-url>

Rules:

* Do not send password reset email synchronously inside request.
* Forgot-password must return 202 fast.
* User-facing response must remain generic.
* Do not expose account existence.
* Do not log reset token.
* Do not show "An unexpected error occurred" for timeout/network failures.
* Backend is source of truth.
* Frontend only calls backend and displays correct state.

Return:

* Root cause confirmed
* Files changed
* New Celery task name
* Email backend config added
* Response examples
* Timeout behavior before/after
* Validation results
* Suggested backend branch/commit
* Suggested frontend branch/commit
