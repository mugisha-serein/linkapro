"""OAuth provider value object."""
from enum import Enum


class OAuthProvider(str, Enum):
    GOOGLE = "google"
