Fix LinkaPro FastAPI marketplace CORS and 500 error for custom domain https://www.linkapro.rw.

Problem:
Frontend marketplace request fails:

Access to XMLHttpRequest at
https://linkapro-fastapi.onrender.com/api/v1/marketplace/search?page=1
from origin https://www.linkapro.rw has been blocked by CORS policy:
No Access-Control-Allow-Origin header is present.

Also:
GET /api/v1/marketplace/search?page=1 net::ERR_FAILED 500

Root cause:
FastAPI CORS config does not include the custom production domain https://www.linkapro.rw / https://linkapro.rw. The browser reports CORS, but the endpoint is also returning 500, likely because marketplace search dependencies such as Redis or database config fail.

Repository:

* Backend: linkapro

Files to inspect:

* fastapi_app/main.py
* fastapi_app/config.py
* fastapi_app/dependencies.py
* fastapi_app/database.py
* fastapi_app/routers/marketplace.py
* application/marketplace/search_service.py
* requirements/fastapi.txt
* Render env documentation

Tasks:

1. Fix FastAPI production CORS origins.
   In fastapi_app/config.py, update production default origins to include:

   * https://www.linkapro.rw
   * https://linkapro.rw
   * https://linkapro.vercel.app

2. Also keep support for FASTAPI_CORS_ORIGINS env var.

3. Ensure production requires custom domain origins.
   If FASTAPI_ENV=production, get_cors_origins should require:

   * https://www.linkapro.rw
   * https://linkapro.rw
   * https://linkapro.vercel.app

4. Error message should clearly name missing origins.

5. Confirm CORSMiddleware wraps all responses.
   Ensure app.add_middleware(CORSMiddleware, ...) is registered before routers and exception handlers are okay.
   Error responses should still include CORS headers when Origin is allowed.

6. Fix FastAPI Redis TLS config.
   Current dependency uses:
   Redis.from_url(redis_url, decode_responses=True)

   For rediss:// Upstash URL:

   * env URL should use ssl_cert_reqs=required
   * normalize CERT_REQUIRED to required if accidentally configured
   * do not use CERT_NONE in production
   * do not log Redis password

   Add helper:

   * normalize_redis_url
   * mask_redis_url_for_logs

7. Make Redis cache/rate limiting fail soft for marketplace search.
   Marketplace search should work even if Redis cache is unavailable.
   If Redis.from_url or ping/cache operations fail:

   * log marketplace_redis_unavailable
   * skip cache/rate limiting
   * continue database search
   * do not return 500 just because Redis cache failed

   Redis should not be required for public marketplace browsing.

8. Fix database 500 if present.
   Inspect fastapi_app/database.py.
   Ensure FastAPI uses async SQLAlchemy URL:

   * postgresql+asyncpg://...

   If DATABASE_URL is postgresql://, convert it safely for FastAPI or require FASTAPI_DATABASE_URL.

   Startup/check should give clear error:
   "FASTAPI_DATABASE_URL must use postgresql+asyncpg://"

9. Improve marketplace search error logging.
   In /api/v1/marketplace/search:

   * log request_id
   * log safe reason for DB/Redis/config failure
   * return JSON error with request_id
   * do not leak secrets

10. Add tests.

    * get_cors_origins includes https://www.linkapro.rw
    * production config fails if custom domain origins missing
    * CORS preflight from https://www.linkapro.rw returns allow-origin
    * search endpoint returns CORS headers on error
    * Redis unavailable does not make search return 500
    * bad Redis TLS string CERT_REQUIRED is normalized to required
    * database URL validation requires async driver
    * marketplace health returns ok when schema exists

11. Render env documentation.
    FastAPI service env must include:
    FASTAPI_ENV=production
    FASTAPI_CORS_ORIGINS=https://www.linkapro.rw,https://linkapro.rw,https://linkapro.vercel.app
    REDIS_URL=rediss://default:@relevant-eft-112987.upstash.io:6379?ssl_cert_reqs=required
    FASTAPI_DATABASE_URL=postgresql+asyncpg://:@/

12. Validation commands.
    python -m pytest tests/fastapi_app -q
    python -c "from fastapi_app.config import get_cors_origins; print(get_cors_origins())"

Manual:
curl -i "https://linkapro-fastapi.onrender.com/api/v1/marketplace/search?page=1" -H "Origin: https://www.linkapro.rw"
curl -i "https://linkapro-fastapi.onrender.com/api/v1/marketplace/health" -H "Origin: https://www.linkapro.rw"

Rules:

* Custom domain https://www.linkapro.rw must be allowed.
* Public marketplace search must not fail just because Redis cache/rate limiting fails.
* Do not log Redis or DB secrets.
* Use rediss ssl_cert_reqs=required in URL.
* Use postgresql+asyncpg:// for FastAPI database.
* Backend is source of truth.

Return:

* Root cause
* Files changed
* Required Render env vars
* CORS test result
* Marketplace search test result
* Validation results
* Suggested branch and commit message
