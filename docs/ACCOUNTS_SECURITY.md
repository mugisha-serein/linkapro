# LinkaPro Accounts App - Complete Security System Documentation

**Version**: 2.0  
**Last Updated**: April 2026  
**Scope**: Django accounts app security architecture, authentication flows, and security enhancements  
**Updated With**: Anomaly detection, Redis health monitoring, JWT key rotation, HaveIBeenPwned integration, penetration tests

---

## Table of Contents

1. [System Architecture](#1-system-architecture)
2. [User Model & Roles](#2-user-model--roles)
3. [Authentication & JWT](#3-authentication--jwt)
4. [Password Security](#4-password-security)
5. [Rate Limiting](#5-rate-limiting)
6. [Session Management & Token Revocation](#6-session-management--token-revocation)
7. [OAuth2 Security](#7-oauth2-security)
8. [Anomaly Detection (New Country Login)](#8-anomaly-detection--new-country-login)
9. [Redis Health Monitoring](#9-redis-health-monitoring)
10. [JWT Key Rotation Strategy](#10-jwt-key-rotation-strategy)
11. [API Endpoints Reference](#11-api-endpoints-reference)
12. [Error Codes](#12-error-codes)
13. [Setup & Configuration](#13-setup--configuration)
14. [Security Checklist](#14-security-checklist)
15. [Testing & Penetration Tests](#15-testing--penetration-tests)
16. [Troubleshooting](#16-troubleshooting)

---

## 1. System Architecture

### Two-Layer Auth System

```
┌─────────────────────────────────────────────────────────────────┐
│                        CLIENT (Browser / App)                   │
└─────────────────────────┬───────────────────────────────────────┘
                          │ HTTPS
          ┌───────────────▼────────────────┐
          │          Nginx (Reverse Proxy)  │
          │     SSL Termination + Routing   │
          └──────────┬──────────┬───────────┘
                     │          │
       ┌─────────────▼──┐  ┌────▼──────────────┐
       │  Django Auth   │  │  FastAPI Gateway   │
       │  Engine        │  │  (Auth Middleware)  │
       │                │  │                    │
       │ • Registration │  │ • Token Verification│
       │ • Login/Logout │  │ • Role Injection    │
       │ • Token Issue  │  │ • Search Endpoints  │
       │ • Anomaly Detect  │ • Upload Handling   │
       │ • Key Rotation │  │                    │
       └───────┬────────┘  └──────┬─────────────┘
               │                  │
       ┌───────▼──────────────────▼───────┐
       │     PostgreSQL Database           │
       │  (Users, Roles, Profiles,         │
       │   Login Activity, Audit Logs)     │
       └───────────────┬───────────────────┘
                       │
       ┌───────────────▼───────────────────┐
       │              Redis                 │
       │  • JWT Revocation (JTI)            │
       │  • Password Reset Tokens           │
       │  • Session Registry                │
       │  • Rate Limit Counters             │
       │  • Anomaly Detection Cache         │
       │  • Celery Task Broker              │
       └───────────────────────────────────┘
```

---

## 2. User Model & Roles

### Core User Model

**Email-based authentication** (no username field):
- `id`: UUID primary key (non-guessable, globally unique)
- `email`: Unique identifier, required
- `role`: Immutable after creation (PLANNER, VENDOR, ADMIN)
- `is_verified`: Email verification flag (required for login)
- `is_active`: Account status
- `is_staff`: Django admin access flag

### Roles

| Role | Can Register | Can Login | Default Profile | Marketplace Visible |
|------|---|---|---|---|
| **PLANNER** | ✅ Via public API | ✅ (if verified) | PlannerProfile | On approval |
| **VENDOR** | ✅ Via public API | ✅ (if verified) | VendorProfile (DRAFT) | After approval |
| **ADMIN** | ❌ Via API only | ✅ | AdminProfile | Internal only |

### Auto-Created Profiles

- **PlannerProfile**: Full name, avatar, timezone, notification preferences
- **VendorProfile**: Business name, category, approval status (DRAFT/PENDING/APPROVED/REJECTED/SUSPENDED)
- **AdminProfile**: Internal admin metadata

### Role Immutability

**Critical Security**: User role **cannot** be changed after account creation, not even by the user or admin via API. Role changes require direct database modification to prevent privilege escalation.

---

## 3. Authentication & JWT

### JWT Design

**Algorithm**: RS256 (RSA asymmetric signing)
- **Private Key**: Held only by Django (signs tokens)
- **Public Key**: Shared with FastAPI (verifies tokens)
- This design enables FastAPI to verify tokens without calling Django

### Token Lifetimes

| Token | Lifetime | Storage | Secure Flag |
|---|---|---|---|
| Access | 15 minutes | Memory | HttpOnly (not localStorage) |
| Refresh | 7 days | HttpOnly Cookie | Secure; SameSite=Strict |

### JWT Payload Example

```json
{
  "user_id": "550e8400-e29b-41d4-a716-446655440000",
  "email": "vendor@example.com",
  "role": "vendor",
  "jti": "unique-token-id-abc123",
  "iat": 1640995200,
  "exp": 1640996100,
  "device_fingerprint": "hash-of-user-agent-ip"
}
```

### Auth Flow

```
User submits email + password
           │
           ▼
Rate limit check (5/min per IP)
           │
           ▼
Authenticate against Django user
           │
    ┌──────▼──────┐
    │ Invalid?→   │ Return generic error
    │             │ (no account vs password hint)
    └─────────────┘
           │
    ┌──────▼──────────────┐
    │ Email verified?      │
    │ (is_verified=True)   │
    └─────────────────────┘
           │
           ▼
Issue JWT access + refresh pair
           │
           ▼
Record login in LoginActivityLog
           │
           ▼
Check for anomalies (new country login)
           │
           ▼
Return tokens + user data
```

### Custom Auth Classes

**`CustomTokenObtainPairView`**: 
- Adds `role` claim to JWT
- Verifies `is_verified` before issuing token
- Passes through rate limiting
- Detects anomalies and queues notifications

**`CustomTokenRefreshView`**:
- Implements per-user rate limiting (10/min)
- Checks token revocation status in Redis

**`CustomJWTAuthentication`**:
- Verifies RS256 signature
- Checks JTI revocation status
- Checks user-level session revocation
- Raises 401 if revoked

---

## 4. Password Security

### Password Policy (12 Character Minimum)

**Enforced on**:
- Registration (all roles)
- Password change
- Password reset confirmation

**Requirements**:
- ✅ Minimum 12 characters
- ✅ Uppercase letter (A-Z)
- ✅ Lowercase letter (a-z)
- ✅ Digit (0-9)
- ✅ Symbol (!@#$%^&*)
- ✅ Not in common password blacklist
- ✅ Not found in HaveIBeenPwned breach database
- ✅ Not similar to username/email (Django validator)

### Common Password Blacklist

30+ passwords blocked (123456, qwerty, password, letmein, etc.)

### Password Hash Storage

- **Algorithm**: Argon2id (Django default)
- **Salted**: Each password has unique salt
- **Verified**: Two hashes of same password will never match
- **Never Logged**: Passwords never appear in logs

### HaveIBeenPwned Breach Check

**Service**: `apps/accounts/services/breach_checker.py`

**How It Works** (k-anonymity):
1. Client password never sent to HaveIBeenPwned
2. Django hashes password with SHA-1
3. Sends only first 5 hex chars of hash to API
4. Receives list of matching suffix:count pairs
5. Checks if full hash appears in results
6. If found, password is rejected

**Failure Handling**: If API is unreachable, registration proceeds (fail open)

**Integration**:
```python
from apps.accounts.validators.password import validate_password_policy

# Automatically checks breach if check_breach=True (default)
validate_password_policy(password, user=None, check_breach=True)
```

---

## 5. Rate Limiting

### Redis-Based Sliding Window

All rate limits use Redis sorted sets (SortedSetRateLimiter) with automatic expiry.

### Limits by Endpoint

| Endpoint | Limit | Window | Scope |
|----------|-------|--------|-------|
| `POST /api/auth/token/` | 5 | 1 minute | Per IP |
| `POST /api/auth/planner/register/` | 5 | 1 minute | Per IP |
| `POST /api/auth/vendor/register/` | 5 | 1 minute | Per IP |
| `POST /api/auth/password-reset/request_reset/` | 1 | 1 hour | Per email |
| `POST /api/auth/token/refresh/` | 10 | 1 minute | Per user |
| `POST /api/auth/user/change_password/` | 5 | 1 hour | Per user |

### Response on Limit Exceeded

```json
HTTP 429 Too Many Requests
{
  "error": "Too many requests. Please try again later.",
  "retry_after_seconds": 45
}
```

### Implementation

```python
from apps.accounts.services.rate_limit_service import rate_limiter, get_client_ip

client_ip = get_client_ip(request)
if not rate_limiter.is_allowed('login', client_ip, limit=5, period_seconds=60):
    return Response({'error': 'Too many requests'}, status=429)
```

---

## 6. Session Management & Token Revocation

### Per-Session Revocation (JTI-Based)

Each token has unique `jti` (JWT ID) claim tracked in Redis:

```
Redis Key: revoked_token:{jti}
TTL: Token's remaining lifetime (up to 7 days)
Value: JSON with revocation metadata
```

### User-Level Revocation (Session Invalidation)

All sessions for a user can be revoked at once:

```
Redis Key: revoked_user:{user_id}
TTL: Refresh token lifetime (7 days)
Value: JSON with revocation time
```

### Logout Endpoints

| Endpoint | Behavior |
|----------|----------|
| `POST /api/auth/user/logout/` | Revoke current session's refresh token only |
| `POST /api/auth/user/logout-all/` | Revoke ALL active sessions for user |

### Session Revocation on Critical Events

- ✅ **Password Reset**: All sessions invalidated (forces re-login)
- ✅ **Account Suspension**: User-level revocation flagged
- ✅ **Password Change**: All sessions invalidated
- ✅ **Explicit Logout**: Individual session revoked
- ✅ **Logout All**: All sessions revoked

### Verification During Request

```python
# JWT validation checks in order:
1. Verify RS256 signature
2. Check token expiry time
3. Check if JTI revoked
4. Check if user-level revocation active
5. Inject user object into request
```

---

## 7. OAuth2 Security

### Flow

```
User clicks "Login with Google"
           │
           ▼
Frontend redirects to Google consent screen
           │
           ▼
Google returns auth code to Django callback
           │
           ▼
Django exchanges code for Google tokens
           │
           ▼
Django gets user email from Google
           │
    ┌──────▼──────────────────────┐
    │ Is email already in DB?      │
    │                              │
YES: Link to existing account      │
    (only if email verified)       │
    │                              │
NO: Create new account with        │
    role from state parameter      │
    └──────┬─────────────────────┘
           │
           ▼
Issue JWT tokens
Log OAuth link event to audit logs
           │
           ▼
Redirect to frontend with tokens
```

### Security Rules

| Rule | Enforcement |
|------|-------------|
| Email Verification Required | OAuth must have verified email, local account must have verified email |
| Explicit Linking Only | No auto-linking; user must be logged in and explicitly approve link |
| State Parameter | Prevents CSRF; includes intended role (planner/vendor) |
| No Auto-Signup | User must have registered locally first (DISABLED feature) |
| Audit Logging | Every OAuth link/unlink logged with timestamp, IP, provider |

### Failed OAuth Scenarios

```
Scenario: Google email unverified
→ Error: "OAuth email must be verified before linking"
Status: 403 Forbidden

Scenario: Existing local account unverified
→ Error: "Local account must verify email before OAuth linking"
Status: 403 Forbidden

Scenario: Trying to auto-link without being logged in
→ Error: "Log in first and explicitly link social account"
Status: 403 Forbidden
```

---

## 8. Anomaly Detection – New Country Login

### Feature

Detects login from a new geographic location and notifies user.

### Components

**1. LoginActivityLog Model** (`apps/accounts/models/login_activity.py`):
```python
- user_id (FK to User)
- ip_address (GenericIPAddressField)
- country_code (ISO 2-letter code, nullable)
- device_fingerprint (hash of User-Agent, IP)
- timestamp (auto_now_add)
- Indexes: (user, -timestamp), (ip_address, -timestamp), (country_code, -timestamp)
```

**2. GeoIP Locator** (`apps/accounts/services/anomaly_detector.py`):
- Uses MaxMind GeoLite2-City database
- Returns ISO country code for IP address
- Gracefully falls back to None if DB unavailable

**3. Anomaly Detection Logic**:
```python
AnomalyDetector.detect_anomalies(user, ip_address, device_fingerprint)

Checks:
  1. Get user's login activity last 30 days
  2. Extract unique countries from activity
  3. Compare current IP's country to list
  4. If NEW country found:
     - Log anomaly event
     - Queue email notification
     - Return anomaly info for response

Returns:
  {
    'user_id': uuid,
    'ip_address': '197.x.x.x',
    'country_code': 'US',
    'anomalies': [
      {
        'type': 'new_location',
        'country_code': 'US',
        'action': 'notify_user'
      }
    ]
  }
```

### Notification Task

**Celery Task**: `apps/accounts/tasks.send_anomaly_notification(user_id, anomaly_type, anomaly_data)`

Sends email to user:
```
Subject: New login location detected
Body: You logged in from [Country] ([IP]) at [Time]
      If this wasn't you, secure your account immediately.
```

### Auto-Cleanup

**Celery Task**: `apps/accounts/tasks.cleanup_old_login_activities()`
- Runs daily at midnight
- Deletes LoginActivityLog entries older than 90 days

### Prerequisites

1. Download GeoLite2-City.mmdb from MaxMind to `./apps/geoip/`
2. Run migration: `python manage.py migrate accounts`
3. Configure Celery beat schedule (see Setup section)

---

## 9. Redis Health Monitoring

### Purpose

Continuous monitoring of Redis connection health for reliable revocation, rate limiting, and caching.

### Service

**`apps/accounts/services/redis_health.py`**: RedisHealthMonitor

### Health Check Components

```python
health = redis_health_monitor.check_health()

Returns:
{
  'healthy': True/False,
  'timestamp': '2026-04-07T14:30:00.123456Z',
  'response_time_ms': 1.23,
  'error': None or error_string,
  'keys_count': 1234  # Approximate
}
```

**Checks Performed**:
1. PING test (basic connectivity)
2. Response time measurement
3. Approximate key count  
4. Exception handling for all failure modes

### Celery Periodic Task

**`apps/accounts/tasks.check_redis_health()`**

Runs every 5 minutes by default. Configured in `config/celery.py`:

```python
app.conf.beat_schedule = {
    'check-redis-health': {
        'task': 'apps.accounts.tasks.check_redis_health',
        'schedule': crontab(minute='*/5'),
    },
}
```

### State Change Logging

Automatic logging when health status changes:
```
Redis connection restored        (unhealthy → healthy)
Redis connection lost: [reason]  (healthy → unhealthy)
```

### Fallback Behavior

If Redis unavailable:
- Rate limiter falls back to in-memory store (suitable for single-server)
- Token revocation falls back to in-memory store
- Anomaly detection logs warning and continues

**⚠️ In-memory fallback is NOT suitable for multi-server deployments.**

---

## 10. JWT Key Rotation Strategy

### Principle

Versioned RSA keys allow rotating signing keys with **zero downtime** and without invalidating existing tokens.

### Key Versioning

Keys stored as `jwt_private_v{N}.pem` and `jwt_public_v{N}.pem`:

```
keys/
  jwt_private_v1.pem    ← Old key (grace period)
  jwt_public_v1.pem
  jwt_private_v2.pem    ← Current key
  jwt_public_v2.pem
  jwt_private.pem       ← Symlink to jwt_private_v2.pem
  jwt_public.pem        ← Symlink to jwt_public_v2.pem
  jwt_key_versions.json ← Version metadata
```

### Rotation Workflow

#### 1. Initiate Rotation

```bash
python manage.py rotate_jwt_keys
```

**Actions**:
- Generate new 4096-bit RSA key pair
- Store as `jwt_private_v{N}.pem`, `jwt_public_v{N}.pem`
- Update symlinks to new version
- Record rotation event

#### 2. Check Status

```bash
python manage.py rotate_jwt_keys --status
```

**Output**:
```
=== JWT Key Status ===
Current version: 2
Valid key versions: [1, 2]
```

#### 3. Deploy New Key (FastAPI)

Copy `jwt_public_v{N}.pem` to FastAPI servers and restart services.

#### 4. Monitor Grace Period

For 7 days (default):
- **New tokens** signed with v2
- **Old tokens** (v1) still valid
- **Verification** accepts both keys

#### 5. Cleanup After Grace Period

```bash
python manage.py rotate_jwt_keys --cleanup
```

Removes keys older than the last 2 versions.

### Verification During Grace Period

FastAPI verifies tokens against multiple valid keys:

```python
valid_keys = {
    1: public_key_v1,  # Previous (grace period)
    2: public_key_v2   # Current
}

def verify_token(token):
    for version in [2, 1]:  # Try current first
        try:
            return jwt.decode(token, valid_keys[version], alg='RS256')
        except InvalidSignature:
            continue
    raise InvalidToken()
```

### Emergency Rotation (Compromised Key)

If key is compromised:

```bash
# 1. Revoke all active tokens
python manage.py revoke_all_tokens

# 2. Force immediate rotation
python manage.py rotate_jwt_keys --force

# 3. Require re-authentication
```

### Management Command

**`apps/accounts/management/commands/rotate_jwt_keys.py`**

```
Options:
  --status     Show current key version and valid versions
  --force      Force rotation even if recently rotated
  --cleanup    Remove old keys (keep last 2 versions)
```

### Implementation

**`apps/accounts/services/jwt_key_rotation.py`**: JWTKeyRotationManager

```python
# Generate new keys
JWTKeyRotationManager.generate_key_pair(version=2)

# Get current version
current = JWTKeyRotationManager.get_current_version()

# Get all valid keys for verification
valid_keys = JWTKeyRotationManager.get_all_valid_public_keys()

# Cleanup old keys
JWTKeyRotationManager.cleanup_old_keys(keep_versions=2)
```

---

## 11. API Endpoints Reference

### Authentication Endpoints

| Method | Endpoint | Auth | Description | Rate Limit |
|--------|----------|------|-------------|-----------|
| `POST` | `/api/auth/planner/register/` | None | Register planner account | 5/min per IP |
| `POST` | `/api/auth/vendor/register/` | None | Register vendor account | 5/min per IP |
| `POST` | `/api/auth/token/` | None | Login (get JWT pair) | 5/min per IP |
| `POST` | `/api/auth/token/refresh/` | Refresh | Refresh access token | 10/min per user |
| `POST` | `/api/auth/user/logout/` | Bearer | Logout current session | None |
| `POST` | `/api/auth/user/logout-all/` | Bearer | Logout all devices | None |
| `GET` | `/api/auth/user/me/` | Bearer | Get current user profile | None |
| `PATCH` | `/api/auth/user/me/` | Bearer | Update profile | None |
| `POST` | `/api/auth/user/change_password/` | Bearer | Change password (logged in) | 5/hour per user |
| `GET` | `/api/auth/user/sessions/` | Bearer | List active sessions | None |
| `DELETE` | `/api/auth/user/sessions/{id}/` | Bearer | Revoke specific session | None |

### Password Reset Endpoints

| Method | Endpoint | Auth | Description | Rate Limit |
|--------|----------|------|-------------|-----------|
| `POST` | `/api/auth/password-reset/request_reset/` | None | Request reset email | 1/hour per email |
| `POST` | `/api/auth/password-reset/confirm_reset/` | None | Submit new password with token | None |

### OAuth Endpoints

| Method | Endpoint | Auth | Description |
|--------|----------|------|-------------|
| `POST` | `/api/auth/auth/google/` | None | Google OAuth login/signup |
| `POST` | `/api/auth/auth/google/link/` | Bearer | Link Google to existing account |
| `DELETE` | `/api/auth/auth/google/unlink/` | Bearer | Unlink Google from account |

### Admin Endpoints (Future)

Available only with `IsAdminUser` permission (ADMIN role + is_staff=True):

- `GET /api/admin/vendors/queue/` - Pending approvals
- `POST /api/admin/vendors/{id}/approve/` - Approve vendor
- `POST /api/admin/vendors/{id}/reject/` - Reject vendor
- `POST /api/admin/users/{id}/ban/` - Ban user
- etc.

---

## 12. Error Codes

| HTTP Code | Error Code | Scenario |
|-----------|-----------|----------|
| `400` | `validation_error` | Invalid input fields |
| `400` | `password_mismatch` | Passwords don't match |
| `400` | `email_already_registered` | Email taken |
| `400` | `breach_password` | Password found in breaches (HaveIBeenPwned) |
| `401` | `token_expired` | Access token past expiry |
| `401` | `token_invalid` | Malformed or bad signature |
| `401` | `token_revoked` | Token revoked by user or admin |
| `401` | `session_ended` | Session explicitly revoked |
| `401` | `credentials_invalid` | Wrong email or password (generic) |
| `403` | `account_banned` | User is banned |
| `403` | `account_suspended` | User is temporarily suspended |
| `403` | `vendor_not_approved` | Vendor not approved yet |
| `403` | `insufficient_role` | Right auth but wrong role |
| `404` | `resource_not_found` | Entity not found or not accessible |
| `429` | `rate_limit_exceeded` | Too many requests |

---

## 13. Setup & Configuration

### Prerequisites

```bash
# Install dependencies
pip install -r requirements.txt

# Download GeoIP database
wget -O apps/geoip/GeoLite2-City.mmdb \
  https://download.maxmind.com/app/geoip_download?edition_id=GeoLite2-City&...
```

### Environment Variables

```bash
# Django
DEBUG=False
SECRET_KEY=<long-random-key>
ALLOWED_HOSTS=linkapro.rw,api.linkapro.rw
DATABASE_URL=postgresql://user:password@localhost:5432/linkapro_db

# Redis
REDIS_HOST=localhost
REDIS_PORT=6379
REDIS_PASSWORD=<strong-password>
REDIS_DB=0

# JWT
JWT_PRIVATE_KEY_PATH=keys/jwt_private.pem
JWT_PUBLIC_KEY_PATH=keys/jwt_public.pem

# Email
EMAIL_HOST=smtp.sendgrid.net
EMAIL_PORT=587
EMAIL_HOST_USER=apikey
EMAIL_HOST_PASSWORD=<sendgrid-key>
DEFAULT_FROM_EMAIL=noreply@linkapro.rw

# Celery
CELERY_BROKER_URL=redis://localhost:6379/1
CELERY_RESULT_BACKEND=redis://localhost:6379/2
```

### Database Migrations

```bash
python manage.py migrate accounts
```

Creates:
- `LoginActivityLog` table (with 3 performance indexes)
- User profiles (PlannerProfile, VendorProfile, AdminProfile)

### JWT Key Generation

```bash
# Generate initial keys (v1)
openssl genrsa -out keys/jwt_private_v1.pem 4096
openssl rsa -in keys/jwt_private_v1.pem -pubout -out keys/jwt_public_v1.pem

# Create symlinks
ln -s jwt_private_v1.pem keys/jwt_private.pem
ln -s jwt_public_v1.pem keys/jwt_public.pem
```

### Celery Beat Configuration

In `config/celery.py`:

```python
from celery.schedules import crontab

app.conf.beat_schedule = {
    'check-redis-health': {
        'task': 'apps.accounts.tasks.check_redis_health',
        'schedule': crontab(minute='*/5'),  # Every 5 min
    },
    'cleanup-login-activities': {
        'task': 'apps.accounts.tasks.cleanup_old_login_activities',
        'schedule': crontab(hour=0, minute=0),  # Daily at midnight
    },
}
```

### Email Notification Template

Create `templates/accounts/anomaly_notification.html`:

```html
<h2>New Login Detected</h2>
<p>You logged in from <strong>{{ country }}</strong> ({{ ip_address }}) at {{ timestamp }}</p>
<p>If this wasn't you, <a href="https://linkapro.rw/security/change-password">change your password immediately</a>.</p>
```

---

## 14. Security Checklist

### ✅ Implemented

- [x] Email-based authentication (no username)
- [x] Argon2id password hashing
- [x] JWT RS256 (asymmetric signing)
- [x] Minimum 12-character passwords
- [x] Password complexity rules (uppercase, lowercase, digit, symbol)
- [x] Common password blacklist (30+ entries)
- [x] HaveIBeenPwned breach check (k-anonymity)
- [x] Redis-based token revocation (JTI tracking)
- [x] Per-session revocation
- [x] User-level session invalidation (logout all)
- [x] Session invalidation on password change
- [x] Redis-based rate limiting (sliding window)
- [x] Rate limits on login, register, password reset, refresh
- [x] Generic login failure messages (no enumeration)
- [x] Generic password reset response (no enumeration)
- [x] Admin account creation via Django only (no public API)
- [x] Role immutability (cannot self-change role)
- [x] Unverified users cannot login
- [x] OAuth email verification required
- [x] Explicit OAuth linking (no auto-signup)
- [x] Audit logging for OAuth events
- [x] Anomaly detection (new country login)
- [x] Redis health monitoring (periodic)
- [x] JWT key rotation (versioned, grace period)
- [x] Penetration tests (~40+ test cases)

### ⬜ Future Enhancements

- [ ] Two-Factor Authentication (TOTP)
- [ ] Email verification on registration (OTP or link)
- [ ] Anomaly detection for new device
- [ ] Machine learning-based fraud detection
- [ ] Hardware security module (HSM) for key storage
- [ ] Automated key rotation via Celery

---

## 15. Testing & Penetration Tests

### Test Suite Location

`apps/accounts/tests/test_penetration.py` (~40+ test cases)

### Test Categories

**Authentication Security**
- SQL injection prevention in login
- Brute force rate limiting
- Timing attack resilience
- Email enumeration prevention (password reset)
- Generic error messages
- Unverified user rejection

**Password Security**
- Weak password rejection (all variations)
- Password not in API responses
- Password hash uniqueness

**Token Security**
- Token tampering detection
- Token revocation on logout
- Refresh token rate limiting

**Session Management**
- Concurrent session isolation
- Logout all functionality

**Input Validation**
- Email format validation
- Null byte injection prevention
- Field length limits

**Data Exposure Prevention**
- Password reset tokens never exposed
- Generic error messages
- No sensitive data in responses

**Authorization Control**
- Role immutability enforcement
- Admin endpoint access control

**CSRF Protection**
- CSRF token requirement validation

**OAuth Security**
- Email verification required
- Explicit linking only

### Run All Tests

```bash
pytest apps/accounts/tests/test_penetration.py -v
```

### Run Specific Test Class

```bash
pytest apps/accounts/tests/test_penetration.py::TestAuthenticationSecurity -v
```

### Generate Coverage Report

```bash
pytest apps/accounts/tests/test_penetration.py --cov=apps.accounts --cov-report=html
```

---

## 16. Troubleshooting

### GeoIP Database Not Found

```
Warning: GeoIP2 database not found at ./apps/geoip/GeoLite2-City.mmdb
```

**Solution**:
1. Download GeoLite2-City.mmdb from MaxMind
2. Place in `./apps/geoip/`
3. Restart Django

**Workaround**: Anomaly detection will log warning but continue (no IP lookup).

### HaveIBeenPwned API Timeout

```
Warning: HaveIBeenPwned API check failed: Connection timeout
```

**Solution**:
1. Check network connectivity to api.pwnedpasswords.com
2. Check firewall rules (may need to whitelist domain)
3. Retry registration (API failure is fail-open, allows registration)

### Redis Connection Lost

```
Error: Redis connection lost: Connection error
```

**Solutions**:
1. Check Redis service status: `redis-cli ping`
2. Verify Redis HOST, PORT, PASSWORD in environment
3. Ensure Redis is accessible from Django/FastAPI servers
4. For multi-server: Redis is REQUIRED (no in-memory fallback suitable)

### Key Rotation Symlink Failure

```
Error: Failed to update symlinks: Permission denied
```

**Solution**:
1. Ensure `./keys/` directory exists: `mkdir -p keys`
2. Set proper permissions: `chmod 700 keys`
3. Verify Django process has write access

### Token Verification Fails After Rotation

```
Error: Token has been revoked
```

**Cause**: FastAPI still using old public key

**Solution**:
1. Verify new `jwt_public_v{N}.pem` was copied to FastAPI
2. Restart FastAPI service
3. Check `rotate_jwt_keys --status` to confirm version sync

### Celery Tasks Not Running

```
No logs from check_redis_health task
```

**Solutions**:
1. Verify Celery worker is running
2. Verify Celery Beat scheduler is running
3. Check Celery broker (Redis) is healthy
4. Verify beat schedule is configured in `config/celery.py`

---

## Quick Reference

### Common Commands

```bash
# Rotate JWT keys
python manage.py rotate_jwt_keys

# Show key status
python manage.py rotate_jwt_keys --status

# Cleanup old keys
python manage.py rotate_jwt_keys --cleanup

# Run migrations
python manage.py migrate accounts

# Run tests
pytest apps/accounts/tests/test_penetration.py -v

# Check Redis health
python manage.py shell
>>> from apps.accounts.services.redis_health import redis_health_monitor
>>> print(redis_health_monitor.check_health())
```

### Key Files

| File | Purpose |
|------|---------|
| `apps/accounts/models/user.py` | Custom User model |
| `apps/accounts/validators/password.py` | Password policy & breach check |
| `apps/accounts/api/auth_views.py` | Auth endpoints & rate limiting |
| `apps/accounts/tokens/jwt.py` | Custom JWT auth & revocation |
| `apps/accounts/tokens/blacklist.py` | Token revocation storage |
| `apps/accounts/services/anomaly_detector.py` | Anomaly detection logic |
| `apps/accounts/services/redis_health.py` | Redis health monitoring |
| `apps/accounts/services/jwt_key_rotation.py` | Key rotation management |
| `apps/accounts/services/breach_checker.py` | HaveIBeenPwned integration |
| `apps/accounts/tests/test_penetration.py` | Security test suite |

### Key Configuration

**Django Settings** (`config/settings.py`):
```python
SIMPLE_JWT = {
    'ALGORITHM': 'RS256',
    'SIGNING_KEY': JWT_PRIVATE_KEY,
    'VERIFYING_KEY': JWT_PUBLIC_KEY,
    'ACCESS_TOKEN_LIFETIME': timedelta(minutes=15),
    'REFRESH_TOKEN_LIFETIME': timedelta(days=7),
}
```

**Rate Limiting**: `apps/accounts/services/rate_limit_service.py`

**Anomaly Detection**: Enable/disable in `anomaly_detector.py`

---

## Support & Escalation

For security issues:
1. Check [Troubleshooting](#16-troubleshooting) section
2. Review relevant error codes in [Error Codes](#12-error-codes)
3. Check Redis health: `python manage.py shell`
4. Review logs in Django and Celery worker
5. Run penetration tests to validate setup
