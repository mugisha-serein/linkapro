Fix LinkaPro identity token environment so password reset/email verification/2FA tokens do not depend on PAYMENT_ENV.

Problem:
`JWTTokenService._token_env()` currently reads `PAYMENT_ENV`. This is semantically wrong because identity/security tokens are not payment tokens.

Current behavior:

* Password reset token includes `env` from PAYMENT_ENV.
* Email verification token includes `env` from PAYMENT_ENV.
* 2FA temp token includes `env` from PAYMENT_ENV.
* Verification rejects tokens if token env != current PAYMENT_ENV.
* If PAYMENT_ENV changes from test to live, existing password reset links can become invalid even though identity environment did not change.

Repository:

* Backend: linkapro

Files to inspect:

* infrastructure/adapters/jwt_token_service.py
* django_app/settings/base.py
* django_app/settings/production.py
* django_app/settings/development.py
* django_app/settings/test.py if present
* tests/infrastructure/adapters/test_jwt_token_service.py
* identity forgot/reset password tests
* any code relying on PAYMENT_ENV in JWT claims

Goal:
Separate identity token environment from payment environment.

Backend tasks:

1. Add dedicated identity token environment setting.
   In settings, add:

   TOKEN_ENV = os.environ.get(
   "TOKEN_ENV",
   os.environ.get("APP_ENV", os.environ.get("DJANGO_ENV", "development" if DEBUG else "production"))
   )

   Or equivalent clean helper.

   Requirements:

   * Production should default to "production" if not explicitly set.
   * Development should default to "development".
   * Test should default to "test".
   * Do not read PAYMENT_ENV for identity token environment.
   * Keep PAYMENT_ENV only for payments.

2. Update JWTTokenService.
   Replace `_token_env()` behavior.

   Current:

   * reads settings.PAYMENT_ENV

   New:

   * reads settings.TOKEN_ENV
   * if missing/empty, raise clear ValueError:
     "TOKEN_ENV must be configured"

   All identity/security tokens should use TOKEN_ENV:

   * access tokens
   * refresh tokens
   * password reset tokens
   * email verification tokens
   * 2FA temp tokens

3. Backward compatibility plan.
   Decide how to handle currently issued tokens that used PAYMENT_ENV.

   Safe short-term approach:

   * For password reset/email verification/2FA tokens, accept either:
     a) current TOKEN_ENV
     b) legacy PAYMENT_ENV only during a short transitional window
   * Log event:
     legacy_identity_token_env_accepted
   * Do not create new tokens with PAYMENT_ENV.
   * Optionally remove legacy acceptance later.

   More strict approach:

   * Do not accept legacy PAYMENT_ENV.
   * Existing links become invalid.

   Recommended:

   * Accept legacy PAYMENT_ENV for password reset/email verification for 24–72 hours or until deployment stabilizes.
   * Do not accept legacy for long-term session tokens if security policy says no.
   * Add clear TODO/comment with removal date or setting:
     ACCEPT_LEGACY_PAYMENT_ENV_TOKENS = os.environ.get("ACCEPT_LEGACY_PAYMENT_ENV_TOKENS", "true").lower() == "true"

4. Avoid breaking logged-in sessions unexpectedly.
   Access/refresh tokens may currently carry PAYMENT_ENV.
   If you change verification for auth tokens, ensure authenticated users are not immediately logged out unless intended.
   Search all token verification/authentication code:

   * HardenedJWTAuthentication
   * auth session facade
   * refresh token handling
   * token blacklist/family logic

   Apply a safe transition if these tokens also enforce env.

5. Add production config validation.
   In production settings:

   * TOKEN_ENV should be set or default to production.
   * It must not equal empty string.
   * It must not be derived from PAYMENT_ENV.
   * PAYMENT_ENV can remain test/live for payment behavior only.

6. Update documentation / Render env.
   Add:
   TOKEN_ENV=production

   Keep:
   PAYMENT_ENV=test or live depending on Flutterwave mode

   Explain:

   * TOKEN_ENV controls identity/security token validity.
   * PAYMENT_ENV controls payment provider mode.
   * Changing PAYMENT_ENV must not invalidate password reset links.

7. Update tests.
   Add/update tests:

   * create_password_reset_token uses TOKEN_ENV, not PAYMENT_ENV
   * changing PAYMENT_ENV does not invalidate password reset token
   * changing TOKEN_ENV does invalidate password reset token
   * email verification token uses TOKEN_ENV
   * temp 2FA token uses TOKEN_ENV
   * access/refresh tokens use TOKEN_ENV
   * legacy PAYMENT_ENV token accepted only when compatibility flag is enabled
   * legacy token rejected when compatibility flag disabled
   * TOKEN_ENV missing raises clear error if applicable

8. Security logging.
   Add structured logs for:

   * identity_token_env_mismatch
   * legacy_identity_token_env_accepted
   * identity_token_env_missing

   Do not log token contents.

9. Validation commands.
   Run:
   python manage.py check
   pytest tests/infrastructure/adapters/test_jwt_token_service.py tests/django_app/identity -q

10. Deployment check.
    In Render env for Django web and Celery worker/beat, set:
    TOKEN_ENV=production

Leave payment env separate:
PAYMENT_ENV=test or PAYMENT_ENV=live depending on current payment mode.

Rules:

* Identity tokens must not depend on PAYMENT_ENV.
* PAYMENT_ENV remains only for payments.
* New identity tokens must be minted with TOKEN_ENV.
* Existing reset links should not be invalidated unnecessarily during migration.
* Do not log tokens.
* Keep password reset secure and predictable.

Return:

* Root cause
* Files changed
* New settings added
* Backward compatibility decision
* Tests added
* Render env changes
* Validation results
* Suggested branch and commit message
