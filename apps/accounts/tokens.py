import redis
import uuid
import json
from django.conf import settings
from django.utils import timezone
from datetime import timedelta


class RedisTokenManager:
    """
    Manages password reset tokens stored in Redis.
    Tokens expire after 24 hours.
    """
    
    PREFIX = "password_reset:"
    EXPIRATION_HOURS = 24
    
    def __init__(self):
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
        except redis.ConnectionError:
            # Fallback to in-memory storage if Redis is not available
            self.redis_client = None
            self._memory_store = {}
    
    def create_token(self, user_id, user_email):
        """
        Create a new password reset token for a user.
        Returns the token string.
        """
        token = str(uuid.uuid4())
        key = f"{self.PREFIX}{token}"
        
        data = {
            'user_id': str(user_id),
            'email': user_email,
            'created_at': timezone.now().isoformat()
        }
        
        if self.redis_client:
            # Store in Redis with expiration
            self.redis_client.setex(
                key,
                timedelta(hours=self.EXPIRATION_HOURS),
                json.dumps(data)
            )
        else:
            # Store in memory (for development/testing)
            expiration = timezone.now() + timedelta(hours=self.EXPIRATION_HOURS)
            self._memory_store[key] = {
                'data': data,
                'expires_at': expiration
            }
        
        return token
    
    def verify_token(self, token):
        """
        Verify a token and return the user data if valid.
        Returns dict with user_id and email, or None if invalid/expired.
        """
        key = f"{self.PREFIX}{token}"
        
        if self.redis_client:
            data = self.redis_client.get(key)
            if not data:
                return None
            return json.loads(data)
        else:
            # Check memory store
            if key not in self._memory_store:
                return None
            
            entry = self._memory_store[key]
            if timezone.now() > entry['expires_at']:
                del self._memory_store[key]
                return None
            
            return entry['data']
    
    def invalidate_token(self, token):
        """
        Invalidate a token by deleting it from Redis.
        """
        key = f"{self.PREFIX}{token}"
        
        if self.redis_client:
            self.redis_client.delete(key)
        else:
            self._memory_store.pop(key, None)
    
    def is_token_valid(self, token):
        """
        Check if a token exists and is valid.
        """
        return self.verify_token(token) is not None
