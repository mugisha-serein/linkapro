from __future__ import annotations

from typing import Protocol
import uuid

class InquiryAbuseProtectionPort(Protocol):
    def assert_inquiry_allowed(
        self,
        *,
        requester_identity: uuid.UUID,
        vendor_id: uuid.UUID,
        payload_digest: str,
    ) -> None: ...
