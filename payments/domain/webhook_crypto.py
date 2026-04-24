"""Domain service for webhook payload decryption policy."""
from dataclasses import dataclass
from typing import Optional


@dataclass(frozen=True)
class DecryptionResult:
    success: bool
    decrypted_data: Optional[dict] = None
    error: Optional[str] = None