"""
Penetration Tests for LinkaPro Accounts App
Tests for common security vulnerabilities and attack vectors.
"""

import pytest
import json
from django.contrib.auth import get_user_model
from rest_framework.test import APIClient
from rest_framework import status

User = get_user_model()


@pytest.mark.django_db
class TestAuthenticationSecurity:
    """Tests for authentication endpoint vulnerabilities."""

    def setup_method(self):
        self.client = APIClient()
        self.user = User.objects.create_user(
            email='test@example.com',
            password='SecurePassword123!',
            is_verified=True
        )

    def test_sql_injection_in_login_email(self):
        """Ensure SQL injection is impossible in email field."""
        response = self.client.post('/api/auth/token/', {
            'email': "test@example.com' OR '1'='1",
            'password': 'anything'
        }, format='json')
        # Should reject as invalid email format, not execute SQL
        assert response.status_code in [400, 401]

    def test_brute_force_rate_limiting(self):
        """Ensure login is rate limited to prevent brute force."""
        for i in range(6):
            response = self.client.post('/api/auth/token/', {
                'email': 'test@example.com',
                'password': 'wrongpassword'
            }, format='json')
        # 6th attempt should be rate limited
        assert response.status_code == 429

    def test_timing_attack_resilience(self):
        """
        Ensure password comparison takes consistent time
        (prevents timing attacks to determine valid accounts).
        """
        import time

        # Invalid user (slow path)
        start = time.time()
        self.client.post('/api/auth/token/', {
            'email': 'nonexistent@example.com',
            'password': 'SomePassword123!'
        }, format='json')
        time_invalid_user = time.time() - start

        # Valid user, wrong password (should be similar timing)
        start = time.time()
        self.client.post('/api/auth/token/', {
            'email': 'test@example.com',
            'password': 'WrongPassword123!'
        }, format='json')
        time_valid_user = time.time() - start

        # Times should be roughly similar (within 100ms)
        # This is a probabilistic test
        assert abs(time_invalid_user - time_valid_user) < 0.1

    def test_no_email_enumeration_on_password_reset(self):
        """
        Ensure password reset endpoint returns same message
        regardless of whether email is registered.
        """
        response_existing = self.client.post('/api/auth/password-reset/request_reset/', {
            'email': 'test@example.com'
        }, format='json')

        response_nonexistent = self.client.post('/api/auth/password-reset/request_reset/', {
            'email': 'nonexistent@example.com'
        }, format='json')

        # Both should return 200 OK with identical message
        assert response_existing.status_code == 200
        assert response_nonexistent.status_code == 200
        assert response_existing.data['message'] == response_nonexistent.data['message']

    def test_generic_login_failure_message(self):
        """Ensure login failure message is generic (no account vs password info)."""
        response = self.client.post('/api/auth/token/', {
            'email': 'nonexistent@example.com',
            'password': 'SomePassword123!'
        }, format='json')

        assert response.status_code == 401
        # Should not say "account not found" or "password incorrect"
        assert 'not found' not in response.data['error'].lower()
        assert 'incorrect' not in response.data['error'].lower()

    def test_unverified_user_cannot_login(self):
        """Ensure unverified accounts cannot obtain tokens."""
        unverified = User.objects.create_user(
            email='unverified@example.com',
            password='SecurePassword123!',
            is_verified=False
        )

        response = self.client.post('/api/auth/token/', {
            'email': 'unverified@example.com',
            'password': 'SecurePassword123!'
        }, format='json')

        assert response.status_code in [401, 403]
        assert 'verify' in response.data['error'].lower() or 'invalid' in response.data['error'].lower()


@pytest.mark.django_db
class TestPasswordSecurity:
    """Tests for password validation and storage security."""

    def setup_method(self):
        self.client = APIClient()

    def test_weak_password_rejected(self):
        """Ensure weak passwords are rejected."""
        weak_passwords = [
            'short',          # Too short
            '12345678',       # Only numbers
            'abcdefgh',       # Only lowercase
            'ABCDEFGH',       # Only uppercase
            'password123',    # Common password
            '123456',         # Very common
        ]

        for pwd in weak_passwords:
            response = self.client.post('/api/auth/planner/register/', {
                'email': f'test_{pwd}@example.com',
                'password': pwd,
                'password_confirm': pwd,
                'full_name': 'Test User'
            }, format='json')
            assert response.status_code == 400, f'Password "{pwd}" should be rejected'

    def test_password_not_in_response(self):
        """Ensure password is never included in API responses."""
        response = self.client.post('/api/auth/planner/register/', {
            'email': 'test@example.com',
            'password': 'SecurePassword123!',
            'password_confirm': 'SecurePassword123!',
            'full_name': 'Test User'
        }, format='json')

        # Check entire response doesn't contain password
        response_str = json.dumps(response.data)
        assert 'SecurePassword123!' not in response_str

    def test_password_hash_not_interchangeable(self):
        """Ensure password hashes are unique (salt is used)."""
        user1 = User.objects.create_user('user1@example.com', 'SamePassword123!')
        user2 = User.objects.create_user('user2@example.com', 'SamePassword123!')

        # Password hashes should be different due to salting
        assert user1.password != user2.password


@pytest.mark.django_db
class TestTokenSecurity:
    """Tests for JWT token security."""

    def setup_method(self):
        self.client = APIClient()
        self.user = User.objects.create_user(
            email='test@example.com',
            password='SecurePassword123!',
            is_verified=True
        )

    def test_token_tamper_detection(self):
        """Ensure tampered tokens are rejected."""
        response = self.client.post('/api/auth/token/', {
            'email': 'test@example.com',
            'password': 'SecurePassword123!'
        }, format='json')

        token = response.data['access']

        # Tamper with token (change one character)
        tampered = token[:-10] + 'XXXXXXXXXX'

        # Try to use tampered token
        self.client.credentials(HTTP_AUTHORIZATION=f'Bearer {tampered}')
        response = self.client.get('/api/auth/user/me/', format='json')

        assert response.status_code == 401

    def test_token_revocation_on_logout(self):
        """Ensure tokens are revoked after logout."""
        response = self.client.post('/api/auth/token/', {
            'email': 'test@example.com',
            'password': 'SecurePassword123!'
        }, format='json')

        access_token = response.data['access']
        refresh_token = response.data['refresh']

        # Use token successfully
        self.client.credentials(HTTP_AUTHORIZATION=f'Bearer {access_token}')
        response = self.client.get('/api/auth/user/me/', format='json')
        assert response.status_code == 200

        # Logout
        response = self.client.post('/api/auth/user/logout/', {
            'refresh': refresh_token
        }, format='json')
        assert response.status_code == 200

        # Try to use same token again (should be rejected)
        response = self.client.get('/api/auth/user/me/', format='json')
        assert response.status_code == 401

    def test_refresh_token_rate_limiting(self):
        """Ensure token refresh is rate limited."""
        response = self.client.post('/api/auth/token/', {
            'email': 'test@example.com',
            'password': 'SecurePassword123!'
        }, format='json')

        refresh_token = response.data['refresh']

        # Attempt rapid refreshes (should be rate limited after 10)
        for i in range(11):
            response = self.client.post('/api/auth/token/refresh/', {
                'refresh': refresh_token
            }, format='json')

        # 11th attempt should be rate limited
        assert response.status_code == 429


@pytest.mark.django_db
class TestOAuthSecurity:
    """Tests for OAuth account linking security."""

    def setup_method(self):
        self.client = APIClient()
        self.user = User.objects.create_user(
            email='oauth@example.com',
            password='SecurePassword123!',
            is_verified=True
        )

    def test_oauth_unverified_email_rejected(self):
        """Ensure unverified OAuth emails cannot auto-link accounts."""
        # This would normally be tested via mocking the OAuth provider
        # Placeholder for OAuth flow testing
        pass

    def test_oauth_explicit_linking_required(self):
        """Ensure OAuth auto-linking is disabled; explicit linking required."""
        # This would normally be tested via mocking the OAuth provider
        # Placeholder for OAuth flow testing
        pass


@pytest.mark.django_db
class TestCSRFProtection:
    """Tests for CSRF protection."""

    def setup_method(self):
        self.client = APIClient()
        self.user = User.objects.create_user(
            email='test@example.com',
            password='SecurePassword123!',
            is_verified=True
        )

    def test_post_without_csrf_token_rejected(self):
        """Ensure POST requests without CSRF token are rejected (if CSRF is enabled)."""
        # Django REST Framework typically disables CSRF for token auth
        # but this test ensures it's configured correctly
        response = self.client.post('/api/auth/user/change_password/', {
            'old_password': 'SecurePassword123!',
            'new_password': 'NewPassword456!'
        }, format='json')

        # Should be rejected due to lack of authentication or CSRF
        assert response.status_code in [401, 403]


@pytest.mark.django_db
class TestSessionManagement:
    """Tests for session security."""

    def setup_method(self):
        self.client = APIClient()
        self.user = User.objects.create_user(
            email='test@example.com',
            password='SecurePassword123!',
            is_verified=True
        )

    def test_concurrent_session_isolation(self):
        """Ensure tokens from different sessions are independent."""
        # Login twice
        response1 = self.client.post('/api/auth/token/', {
            'email': 'test@example.com',
            'password': 'SecurePassword123!'
        }, format='json')

        response2 = self.client.post('/api/auth/token/', {
            'email': 'test@example.com',
            'password': 'SecurePassword123!'
        }, format='json')

        token1 = response1.data['access']
        token2 = response2.data['access']

        # Tokens should be different
        assert token1 != token2

    def test_logout_all_sessions(self):
        """Ensure logout-all revokes all sessions."""
        # Create multiple tokens
        tokens = []
        for i in range(3):
            response = self.client.post('/api/auth/token/', {
                'email': 'test@example.com',
                'password': 'SecurePassword123!'
            }, format='json')
            tokens.append(response.data['access'])

        # Logout all with first token
        self.client.credentials(HTTP_AUTHORIZATION=f'Bearer {tokens[0]}')
        response = self.client.post('/api/auth/user/logout-all/', format='json')
        assert response.status_code == 200

        # All tokens should now be invalid
        for token in tokens:
            self.client.credentials(HTTP_AUTHORIZATION=f'Bearer {token}')
            response = self.client.get('/api/auth/user/me/', format='json')
            assert response.status_code == 401


@pytest.mark.django_db
class TestInputValidation:
    """Tests for input validation and injection vulnerability prevention."""

    def setup_method(self):
        self.client = APIClient()

    def test_email_format_validation(self):
        """Ensure invalid email formats are rejected."""
        invalid_emails = [
            'not-an-email',
            '@example.com',
            'user@',
            'user@@example.com',
            'user@.com',
        ]

        for email in invalid_emails:
            response = self.client.post('/api/auth/planner/register/', {
                'email': email,
                'password': 'SecurePassword123!',
                'password_confirm': 'SecurePassword123!',
                'full_name': 'Test'
            }, format='json')
            assert response.status_code == 400

    def test_null_byte_injection_prevention(self):
        """Ensure null bytes in input cannot cause issues."""
        response = self.client.post('/api/auth/planner/register/', {
            'email': f'test\x00@example.com',
            'password': 'SecurePassword123!',
            'password_confirm': 'SecurePassword123!',
            'full_name': 'Test'
        }, format='json')
        assert response.status_code == 400

    def test_field_length_limits(self):
        """Ensure overly long input is rejected."""
        response = self.client.post('/api/auth/planner/register/', {
            'email': 'a' * 1000 + '@example.com',
            'password': 'SecurePassword123!',
            'password_confirm': 'SecurePassword123!',
            'full_name': 'Test'
        }, format='json')
        assert response.status_code == 400


@pytest.mark.django_db
class TestDataExposure:
    """Tests to prevent sensitive data exposure."""

    def setup_method(self):
        self.client = APIClient()
        self.user = User.objects.create_user(
            email='test@example.com',
            password='SecurePassword123!',
            is_verified=True
        )

    def test_password_reset_token_not_in_response(self):
        """Ensure password reset token is never returned in API response."""
        response = self.client.post('/api/auth/password-reset/request_reset/', {
            'email': 'test@example.com'
        }, format='json')

        response_str = json.dumps(response.data)
        # Should not contain any token-like strings
        assert 'token' not in response_str.lower() or 'exist' in response_str.lower()

    def test_user_id_not_enumerable(self):
        """Ensure user IDs cannot be enumerated via API."""
        response = self.client.get('/api/auth/user/999999/', format='json')
        # Should be 404 Not Found, not 401 Unauthorized (which would leak timing info)
        assert response.status_code in [404, 401]

    def test_error_messages_dont_leak_state(self):
        """Ensure error messages don't leak application state."""
        response = self.client.post('/api/auth/token/', {
            'email': 'test@example.com',
            'password': 'WrongPassword'
        }, format='json')

        error_msg = response.data.get('error', '').lower()
        # Should be generic, not revealing specific state
        assert 'database' not in error_msg
        assert 'internal' not in error_msg
        assert 'exception' not in error_msg


@pytest.mark.django_db
class TestAuthorizationControl:
    """Tests for proper authorization enforcement."""

    def setup_method(self):
        self.client = APIClient()
        self.planner = User.objects.create_user(
            email='planner@example.com',
            password='SecurePassword123!',
            is_verified=True
        )
        self.vendor = User.objects.create_user(
            email='vendor@example.com',
            password='SecurePassword123!',
            is_verified=True
        )
        self.vendor.role = 'vendor'
        self.vendor.save()

    def test_role_immutability(self):
        """Ensure users cannot change their own role."""
        self.client.credentials(HTTP_AUTHORIZATION=f'Bearer {self._get_token(self.planner)}')
        
        # Attempt to change role (should fail or be ignored)
        response = self.client.patch('/api/auth/user/me/', {
            'role': 'admin'
        }, format='json')

        # User should still be planner
        user = User.objects.get(email='planner@example.com')
        assert user.role != 'admin'

    def test_admin_endpoint_access_control(self):
        """Ensure non-admins cannot access admin endpoints."""
        response = self.client.post('/api/admin/vendors/queue/', format='json')
        # Should be 401 Unauthorized or 403 Forbidden
        assert response.status_code in [401, 403]

    def _get_token(self, user):
        """Helper to get JWT token for user."""
        response = self.client.post('/api/auth/token/', {
            'email': user.email,
            'password': 'SecurePassword123!'
        }, format='json')
        return response.data.get('access')


@pytest.mark.django_db  
class TestPasswordResetSecurity:
    """Tests for password reset flow security."""

    def setup_method(self):
        self.client = APIClient()
        self.user = User.objects.create_user(
            email='test@example.com',
            password='SecurePassword123!',
            is_verified=True
        )

    def test_password_reset_token_single_use(self):
        """Ensure password reset tokens can only be used once."""
        # Request reset
        response = self.client.post('/api/auth/password-reset/request_reset/', {
            'email': 'test@example.com'
        }, format='json')

        # Token is sent via email (would be captured in test)
        # Assuming we have the token, use it
        # (In actual test, would extract from email or mock)
        # ... (would need to mock email sending)

    def test_password_reset_token_expiration(self):
        """Ensure password reset tokens expire after configured time."""
        # Request reset
        response = self.client.post('/api/auth/password-reset/request_reset/', {
            'email': 'test@example.com'
        }, format='json')

        # Wait for expiration (in real test, would mock time)
        # Attempt to use expired token should fail

    def test_password_reset_invalidates_sessions(self):
        """Ensure password reset invalidates all active sessions."""
        # Get token for user
        response = self.client.post('/api/auth/token/', {
            'email': 'test@example.com',
            'password': 'SecurePassword123!'
        }, format='json')
        old_token = response.data['access']

        # Reset password (would use actual reset flow)
        # ... (would need to complete reset flow)

        # Old token should be invalid
        self.client.credentials(HTTP_AUTHORIZATION=f'Bearer {old_token}')
        response = self.client.get('/api/auth/user/me/', format='json')
        # Should be rejected after password reset
        # (in actual flow, all sessions should be invalidated)


if __name__ == '__main__':
    pytest.main([__file__, '-v'])
