# LinkaPro Authentication System Architecture

## Overview
The authentication system uses Django's AbstractBaseUser with role-based access control, JWT tokens, and OAuth2 integration via Google.

---

## 1. Core Authentication Components

### 1.1 Custom User Model (`accounts.User`)
- **Base**: `AbstractBaseUser` + `PermissionsMixin`
- **Primary Identifier**: Email (no username)
- **UUID Primary Key**: Globally unique IDs
- **Role Field**: Single immutable role per user
  - `PLANNER` - Event organizers
  - `VENDOR` - Service providers
  - `ADMIN` - System administrators

```python
# Usage
user = User.objects.create_planner(
    email='planner@example.com',
    password='secure_password'
)
```

### 1.2 User Manager Methods
Three specialized creation methods ensure proper role assignment and profile creation:

```python
# Create Planner
User.objects.create_planner(email, password)

# Create Vendor
User.objects.create_vendor(
    email, password,
    business_name='...',
    phone='...',
    location='...'
)

# Create Admin (superuser only)
User.objects.create_admin(email, password)
```

---

## 2. JWT Authentication (SimpleJWT)

### 2.1 Token Management
```python
# Tokens returned on login
{
    "access": "eyJ0eXAiOiJKV1QiLCJhbGc...",     # 15 min lifetime
    "refresh": "eyJ0eXAiOiJKV1QiLCJhbGc..."    # 7 day lifetime
}
```

### 2.2 Token Endpoints
- `POST /api/auth/token/` - Get JWT tokens (email + password)
- `POST /api/auth/token/refresh/` - Refresh access token

### 2.3 Token Features
- Automatic refresh rotation
- Token blacklist on logout
- HS256 signing algorithm
- User ID claim for easy lookups

---

## 3. OAuth2 (Google)

### 3.1 Setup Required
1. Create Google OAuth2 credentials
2. Set environment variables:
   ```bash
   export GOOGLE_OAUTH2_CLIENT_ID="..."
   export GOOGLE_OAUTH2_CLIENT_SECRET="..."
   ```

### 3.2 OAuth Endpoints
- `POST /api/auth/auth/google/` - Login with Google token
- `POST /api/auth/auth/registration/` - Social registration

### 3.3 Features
- Automatic user creation on first login
- Email verification via Google
- Social account linking

---

## 4. Role-Based Permissions

### 4.1 Permission Classes

```python
from accounts.permissions import (
    IsPlannerUser,      # Planner role only
    IsVendorUser,       # Vendor role only
    IsAdminUser,        # Admin role only
    IsVendorOrAdmin,    # Vendor OR Admin
    IsPlannerOrAdmin,   # Planner OR Admin
    IsApprovedVendor,   # Approved vendor only
)
```

### 4.2 Usage in Views

```python
from rest_framework.permissions import IsAuthenticated
from accounts.permissions import IsPlannerUser

class EventListView(viewsets.ModelViewSet):
    permission_classes = [IsAuthenticated, IsPlannerUser]
    # Only authenticated planners can access
```

### 4.3 Permission Logic
```python
# Planner Check
user.role == User.Roles.PLANNER

# Approved Vendor Check
user.role == User.Roles.VENDOR and 
user.vendor_profile.approval_status == 'approved'

# Admin Check
user.role == User.Roles.ADMIN and
user.is_staff == True
```

---

## 5. Password Reset Flow

### 5.1 Two-Step Process
1. **Request Token**: Email → Redis token (24-hour expiration)
2. **Confirm Reset**: Token + new password → password updated

### 5.2 Redis Storage
- Tokens stored in Redis with automatic expiration
- Fast token lookup and validation
- Atomic password update

### 5.3 Endpoints

**Step 1: Request Reset**
```bash
POST /api/auth/password-reset/request_reset/
Content-Type: application/json

{
    "email": "user@example.com"
}

Response:
{
    "message": "Password reset link sent to your email",
    "token": "abc123def456..."  # Remove in production
}
```

**Step 2: Confirm Reset**
```bash
POST /api/auth/password-reset/confirm_reset/
Content-Type: application/json

{
    "token": "abc123def456...",
    "new_password": "newSecurePass123",
    "new_password_confirm": "newSecurePass123"
}

Response:
{
    "message": "Password reset successfully"
}
```

### 5.4 Security Features
- Tokens valid for 24 hours only
- Single-use tokens (invalidated after use)
- Email verification (to be implemented)
- Rate limiting (to be implemented)

---

## 6. Registration Flows

### 6.1 Planner Registration
```bash
POST /api/auth/planner/register/register/
Content-Type: application/json

{
    "email": "planner@example.com",
    "password": "SecurePass123",
    "password_confirm": "SecurePass123",
    "full_name": "John Doe"
}

Response:
{
    "user": {
        "id": "uuid-here",
        "email": "planner@example.com",
        "role": "planner",
        "is_verified": false
    },
    "access": "eyJ0eXAi...",
    "refresh": "eyJ0eXAi..."
}
```

### 6.2 Vendor Registration
```bash
POST /api/auth/vendor/register/register/
Content-Type: application/json

{
    "email": "vendor@example.com",
    "password": "SecurePass123",
    "password_confirm": "SecurePass123",
    "business_name": "Acme Corp",
    "phone": "+1234567890",
    "location": "New York"
}

Response:
{
    "user": {...},
    "access": "...",
    "refresh": "...",
    "message": "Vendor account created successfully. Your profile is in DRAFT status."
}
```

### 6.3 Admin Creation
```bash
POST /api/auth/admin/create/create_admin/
Authorization: Bearer <admin-token>

{
    "email": "admin@example.com",
    "password": "SecureAdminPass123",
    "password_confirm": "SecureAdminPass123"
}

Response:
{
    "user": {...},
    "message": "Admin account created successfully"
}
```

---

## 7. User Profile Endpoints

### 7.1 Get Current User
```bash
GET /api/auth/user/me/
Authorization: Bearer <access-token>

Response:
{
    "id": "uuid",
    "email": "user@example.com",
    "role": "planner",
    "is_active": true,
    "is_verified": false,
    "date_joined": "2024-04-07T..."
}
```

### 7.2 Change Password
```bash
POST /api/auth/user/change_password/
Authorization: Bearer <access-token>

{
    "old_password": "OldPass123",
    "new_password": "NewPass123"
}

Response:
{
    "message": "Password changed successfully"
}
```

---

## 8. Email Verification (Future Phase)

Placeholder for email verification flow:
- Send verification email on registration
- Verify email endpoint
- Resend verification email

---

## 9. Environment Variables

Required for production:
```bash
# Google OAuth
GOOGLE_OAUTH2_CLIENT_ID=...
GOOGLE_OAUTH2_CLIENT_SECRET=...

# Redis
REDIS_HOST=localhost
REDIS_PORT=6379
REDIS_DB=0

# JWT Secret
SECRET_KEY=your-secret-key-here

# Django Settings
DEBUG=False
ALLOWED_HOSTS=yourdomain.com
```

---

## 10. Security Checklist

- [x] Email-based authentication (no username)
- [x] Bcrypt password hashing
- [x] JWT token rotation
- [x] Resource-level permissions
- [x] Role immutability
- [x] Time-limited password reset tokens
- [ ] Email verification on registration
- [ ] Rate limiting on auth endpoints
- [ ] HTTPS in production
- [ ] Secure Redis connection
- [ ] API key rotation strategy

---

## 11. Testing the System

### Create a Planner
```bash
curl -X POST http://localhost:8000/api/auth/planner/register/register/ \
  -H "Content-Type: application/json" \
  -d '{
    "email": "planner@test.com",
    "password": "TestPass123",
    "password_confirm": "TestPass123"
  }'
```

### Login
```bash
curl -X POST http://localhost:8000/api/auth/token/ \
  -H "Content-Type: application/json" \
  -d '{
    "email": "planner@test.com",
    "password": "TestPass123"
  }'
```

### Access Protected Resource
```bash
curl -X GET http://localhost:8000/api/auth/user/me/ \
  -H "Authorization: Bearer <access-token>"
```

---

## 12. API Rate Limiting (Future)

Recommended rates:
- `/token/` - 5 requests per minute per IP
- `/password-reset/request_reset/` - 3 requests per hour per email
- `/planner/register/` - 10 requests per hour per IP
- Other endpoints - 60 requests per minute per user

---

## 13. Troubleshooting

### Redis Connection Error
```
Error: Connection refused
Solution: Start Redis server
redis-server
```

### Token Invalid Error
```
Error: Token is invalid or expired
Solution: Use refresh endpoint to get new access token
```

### Permission Denied
```
Error: 403 Forbidden
Solution: Check user role matches endpoint requirements
```
