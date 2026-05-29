import secrets
import uuid
from django.contrib.auth.hashers import make_password
from django_app.payments.models import ApiKey
from django_app.identity.models import User

def create_api_key(user: User, scopes: list, expires_at=None) -> tuple[str, str]:
    """Generate a new API key. Returns (key_id, secret)."""
    key_id = f"pk_{uuid.uuid4().hex[:16]}"
    secret = secrets.token_hex(32)  # 64 chars
    key_hash = make_password(secret)  # PBKDF2
    ApiKey.objects.create(
        key_id=key_id,
        key_hash=key_hash,
        secret_plain=secret,
        user=user,
        scopes=scopes,
        expires_at=expires_at,
    )
    return key_id, secret
