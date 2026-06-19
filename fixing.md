Fix LinkaPro password reset tokens so reset links are single-use and cannot be reused after a successful password reset.

Problem:
Current password reset flow verifies a JWT reset token and then sets the new password. The token appears reusable until expiry because there is no nonce/jti tracking, password-reset token table, used-token blacklist, reset version, or password timestamp validation.

Current risk:

* User requests password reset.
* User receives reset link.
* User resets password successfully.
* Same reset link can potentially be submitted again before token expiry.
* This is not production-grade security.

Repository:

* Backend: linkapro

Files to inspect:

* infrastructure/adapters/jwt_token_service.py
* django_app/identity/views.py
* django_app/identity/serializers.py
* django_app/identity/models.py
* django_app/identity/urls.py
* application/identity handlers/services if existing
* tests/infrastructure/adapters/test_jwt_token_service.py
* tests/django_app/identity
* migrations

Goal:
Make password reset tokens single-use while keeping the user-facing reset flow simple and secure.

Backend tasks:

1. Inspect current password reset token creation and verification.
   Current code likely:

   * creates JWT with user_id, token_type=password_reset, env, exp, iat
   * verifies JWT and returns user_id
   * ResetPasswordView sets password directly

2. Add a unique reset token identifier.
   Update `create_password_reset_token` to include:

   * jti: UUID string
   * purpose/token_type: password_reset
   * user_id
   * env/TOKEN_ENV
   * exp
   * iat

   Do not log jti with token together.

3. Add persistent token tracking.
   Add model, for example:

   PasswordResetToken

   Fields:

   * id UUID primary key
   * user FK to identity.User
   * jti unique indexed
   * token_hash indexed
   * status: active, used, expired, revoked
   * requested_at
   * used_at nullable
   * expires_at
   * requested_ip_hash nullable
   * requested_user_agent_hash nullable
   * used_ip_hash nullable
   * used_user_agent_hash nullable
   * created_at
   * updated_at

   Security rule:

   * Never store raw reset token.
   * Store a hash of token or jti only.
   * Prefer HMAC hash using SECRET_KEY or a dedicated RESET_TOKEN_HASH_KEY.

4. Token issuance behavior.
   When forgot-password creates a reset token:

   * create JWT with jti
   * store PasswordResetToken row with jti/token_hash, user, active, expires_at
   * enqueue email task with raw token only in task payload
   * do not store raw token in database
   * do not log raw token or reset URL

5. Token verification behavior.
   Add method/service:
   verify_password_reset_token_once(token)

   It should:

   * decode JWT signature and expiry
   * verify token_type=password_reset
   * verify env/TOKEN_ENV
   * extract user_id and jti
   * hash token
   * find active PasswordResetToken row by jti/token_hash/user
   * reject if not active
   * reject if used/revoked/expired
   * reject if expires_at < now
   * return user_id and token record

6. Token consume behavior.
   ResetPasswordView should be atomic:

   * validate serializer
   * verify token once
   * fetch active user
   * set new password
   * mark PasswordResetToken used with used_at
   * optionally revoke other active reset tokens for same user
   * commit transaction

   Use `transaction.atomic()` and row locking:

   * select_for_update() on PasswordResetToken
   * prevents race condition where two requests reuse same token at the same time

7. Reuse response.
   If used token is submitted again, return controlled 400:
   {
   "code": "password_reset_token_invalid",
   "message": "This reset link has expired or is invalid.",
   "field_errors": {
   "token": ["Invalid or expired reset token."]
   }
   }

   Do not say “already used” to avoid leaking token state.

8. Expired token cleanup.
   Add periodic cleanup or management command:

   * expire old active tokens whose expires_at is in the past
   * delete/retain old records according to audit policy

   If Celery beat exists, add task:
   expire_password_reset_tokens_task

   Or management command:
   python manage.py expire_password_reset_tokens

9. Invalidate older active reset links.
   Recommended behavior:

   * When a new reset link is requested, revoke previous active reset tokens for that user.
   * Only the newest reset link remains usable.
   * This avoids multiple reset links being valid at once.

   If this is too disruptive, at least revoke all other active tokens after a successful reset.

10. Password change invalidation.
    Optional extra safety:

* Add password_changed_at field on User if not present.
* Include password_version or password_changed_at timestamp in reset token claims.
* If password changes after token issuance, token becomes invalid.
* This helps invalidate old tokens even if token tracking has an edge case.

Do not overcomplicate if single-use table is enough for this phase.

11. Logging.
    Add structured logs:

* password_reset_token_issued
* password_reset_token_consumed
* password_reset_token_rejected
* password_reset_token_reuse_attempt
* password_reset_token_expired

Do not log:

* raw token
* full reset URL
* password
* full email address

12. Tests.
    Add tests:

* token contains jti
* issuing reset creates PasswordResetToken row
* valid token resets password
* same token cannot be reused
* two concurrent submissions cannot both succeed
* expired token fails
* revoked token fails
* new reset request revokes previous active token
* successful reset marks token used
* inactive user cannot reset
* response for used/revoked/expired token is same generic invalid-token response
* raw token is never stored in database
* raw token is never logged

13. Migration.
    Add migration for PasswordResetToken model.
    Existing users do not need data backfill.
    Existing reset links issued before this deployment may become invalid unless compatibility is implemented.
    Decide and document:

* Strict: old JWT-only reset links are invalid after deploy.
* Transitional: accept legacy JWT-only reset links only for current expiry window, then remove.

Recommended:

* Strict is acceptable if reset timeout is 1 hour.
* Users can request a new reset link.

14. Validation commands.
    Run:
    python manage.py makemigrations identity
    python manage.py check
    pytest tests/django_app/identity tests/infrastructure/adapters/test_jwt_token_service.py -q

Rules:

* Reset tokens must be single-use.
* Do not store raw tokens.
* Do not log raw tokens or full reset URLs.
* Reused/expired/revoked tokens must return same generic invalid-token response.
* Use transaction/locking to prevent race reuse.
* Backend is source of truth.
* Frontend contract can stay the same unless response shape changed.

Return:

* Root cause of reusable reset token
* Files changed
* Migration name
* New model fields
* Token lifecycle
* Reuse/race protection design
* Response examples
* Validation results
* Suggested branch and commit message
