import redis
import json
from datetime import datetime, timedelta
from django.conf import settings
from django.utils import timezone


class RedisTokenRevocationManager:
    """
    Redis-based token revocation system for JWT tokens.
    Tracks revoked tokens by JTI (JWT ID) for efficient validation.
    """

    def __init__(self):
        self.redis_client = None
        self._memory_store = {}
        self._redis_available = False
        
        try:
            self.redis_client = redis.Redis(
                host=getattr(settings, 'REDIS_HOST', 'localhost'),
                port=getattr(settings, 'REDIS_PORT', 6379),
                db=getattr(settings, 'REDIS_DB', 0),
                decode_responses=True,
                socket_connect_timeout=5,
                socket_timeout=5
            )
            # Test connection
            self.redis_client.ping()
            self._redis_available = True
        except redis.ConnectionError:
            # Fallback to in-memory storage if Redis is not available
            self.redis_client = None
            self._redis_available = False

    def revoke_token(self, jti, user_id=None, expiry_timestamp=None):
        """
        Revoke a token by its JTI.
        Stores in Redis with automatic expiry.
        """
        if expiry_timestamp is None:
            # Default to 7 days (refresh token lifetime)
            expiry_timestamp = timezone.now() + timedelta(days=7)

        data = {
            'revoked_at': timezone.now().isoformat(),
            'user_id': str(user_id) if user_id else None,
            'jti': jti
        }

        key = f"revoked_token:{jti}"

        if self._redis_available and self.redis_client:
            # Store in Redis with expiry
            self.redis_client.setex(
                key,
                timedelta(seconds=int((expiry_timestamp - timezone.now()).total_seconds())),
                json.dumps(data)
            )
        else:
            # Store in memory (for development/testing)
            self._memory_store[key] = {
                'data': data,
                'expires_at': expiry_timestamp
            }

    def is_token_revoked(self, jti):
        """
        Check if a token is revoked by its JTI.
        """
        key = f"revoked_token:{jti}"

        if self._redis_available and self.redis_client:
            data = self.redis_client.get(key)
            return data is not None
        else:
            # Check memory store
            if key not in self._memory_store:
                return False

            entry = self._memory_store[key]
            if timezone.now() > entry['expires_at']:
                del self._memory_store[key]
                return False

            return True

    def revoke_user_sessions(self, user_id):
        """
        Revoke all active sessions for a user.
        Stores a user-level revocation marker.
        """
        key = f"revoked_user:{user_id}"
        data = {
            'revoked_at': timezone.now().isoformat(),
            'user_id': str(user_id)
        }

        # User sessions are revoked for at least the configured refresh token lifetime.
        refresh_ttl = getattr(settings, 'SIMPLE_JWT', {}).get('REFRESH_TOKEN_LIFETIME', timedelta(days=7))
        expiry = timezone.now() + refresh_ttl

        if self._redis_available and self.redis_client:
            self.redis_client.setex(
                key,
                timedelta(seconds=int((expiry - timezone.now()).total_seconds())),
                json.dumps(data)
            )
        else:
            self._memory_store[key] = {
                'data': data,
                'expires_at': expiry
            }

    def is_user_revoked(self, user_id):
        """
        Check if a user's sessions are revoked.
        """
        key = f"revoked_user:{user_id}"

        if self._redis_available and self.redis_client:
            data = self.redis_client.get(key)
            return data is not None
        else:
            if key not in self._memory_store:
                return False

            entry = self._memory_store[key]
            if timezone.now() > entry['expires_at']:
                del self._memory_store[key]
                return False

            return True

    def get_revoked_tokens_count(self):
        """
        Get count of currently revoked tokens (for monitoring).
        """
        if self._redis_available and self.redis_client:
            # Count keys matching pattern
            return len(self.redis_client.keys("revoked_token:*"))
        else:
            return len([k for k in self._memory_store.keys() if k.startswith("revoked_token:")])

    def cleanup_expired_tokens(self):
        """
        Clean up expired tokens (Redis handles this automatically,
        but useful for memory store).
        """
        if not self.redis_client:
            current_time = timezone.now()
            expired_keys = [
                key for key, entry in self._memory_store.items()
                if current_time > entry['expires_at']
            ]
            for key in expired_keys:
                del self._memory_store[key]


# Global instance
token_revocation_manager = RedisTokenRevocationManager()