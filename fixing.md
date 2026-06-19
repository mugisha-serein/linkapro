Fix LinkaPro reset-password returning “An unexpected error occurred” by standardizing backend reset-password errors and hardening frontend error extraction.

Problem:
When a user tries to reset password, the form shows “An unexpected error occurred.” This text comes from frontend `apiClient.normalizeAppError`, not from the backend directly. It appears when backend errors do not include `detail`, `error`, or `message`, or when the response is non-JSON/empty/wrong URL.

Repositories:

* Backend: linkapro
* Frontend: linkapro-frontend

Current flow:

* Frontend page: src/app/auth/reset-password/page.tsx
* Frontend service: src/services/authService.ts
* Frontend client/error normalizer: src/services/apiClient.ts and src/lib/apiErrors.ts
* Backend endpoint: POST /api/django/identity/reset-password/
* Backend view: django_app/identity/views.py ResetPasswordView
* Backend serializer: django_app/identity/serializers.py ResetPasswordSerializer

Goal:
Make reset-password errors clear and backend-driven. The frontend should never show “An unexpected error occurred” when backend provides useful password/token validation errors.

Backend tasks:

1. Inspect ResetPasswordView and ResetPasswordSerializer.

2. Stop relying on DRF default serializer error shape for reset-password.
   In ResetPasswordView:

   * instantiate serializer
   * if not valid, return controlled 400:
     {
     "code": "password_reset_invalid",
     "message": "Please fix the highlighted fields.",
     "field_errors": serializer.errors
     }

3. Invalid/expired token should return controlled 400:
   {
   "code": "password_reset_token_invalid",
   "message": "This reset link has expired or is invalid.",
   "field_errors": {
   "token": ["Invalid or expired reset token."]
   }
   }

4. Inactive/missing user should return the same token-invalid response.
   Do not reveal whether user exists.

5. Successful reset remains:
   {
   "status": "password_reset",
   "message": "Password updated successfully."
   }

6. Add structured logging for reset failures:

   * invalid token
   * serializer validation failed
   * user not found/inactive
     Do not log token value or full reset URL.

7. Add backend tests:

   * missing token returns code password_reset_invalid with field_errors.token
   * weak password returns field_errors.new_password
   * invalid token returns password_reset_token_invalid
   * inactive/missing user returns same token invalid response
   * valid token resets password successfully
   * reset response never exposes account existence

Frontend tasks:

8. Inspect current:

   * src/app/auth/reset-password/page.tsx
   * src/lib/apiErrors.ts
   * src/services/apiClient.ts
   * src/services/errors.ts

9. Harden `getApiMessage`.
   Do not let generic AppError message “An unexpected error occurred” override useful field errors.
   Add helper:

   * getFirstApiFieldError(error)
   * getApiCode(error)

10. In reset-password page catch block, handle in this order:

* token/reset_token field errors OR code password_reset_token_invalid -> show expired/invalid link state
* new_password/password field errors -> set password field error
* non_field_errors -> show form error
* backend message/detail/error -> show form error
* fallback -> “We couldn’t update your password right now. Please try again.”

11. Ensure missing token is handled before submit.
    It is already present, but verify it works.

12. Ensure `useWatch` is used, not `watch`.
    It is already present, but verify no React Hook Form compiler warning remains.

13. Add temporary safe console diagnostics only in development:

* status code
* backend code
* field error keys
  Do not log reset token.

14. Verify production API URL.
    Confirm Vercel env:
    NEXT_PUBLIC_API_URL=https://linkapro-django.onrender.com/api/django

If missing, frontend may call /api/django on the frontend domain and receive non-JSON/HTML, causing generic errors.

15. Manual tests:

* /auth/reset-password without token -> invalid link screen
* invalid token -> invalid/expired link screen
* weak backend-rejected password -> password field error
* valid token + valid password -> success screen
* backend 500/network error -> retry message, not “unexpected”
* no token printed in logs

Validation:
Backend:
python manage.py check
pytest tests/django_app/identity -q

Frontend:
npm run lint
npm run build

Rules:

* Frontend only calls backend.
* Backend is source of truth.
* Do not log reset token.
* Do not reveal account existence.
* Do not show generic “An unexpected error occurred” when backend gives useful errors.
* Keep light UI only.

Return:

* Exact root cause found
* Files changed
* Backend response examples
* Frontend error mapping
* Env var/API URL verification
* Validation results
* Suggested branch/commit for backend and frontend
