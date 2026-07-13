from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime
from typing import Optional
import uuid

@dataclass(frozen=True)
class PortfolioImageDTO:
    id: uuid.UUID
    vendor_id: uuid.UUID
    secure_url: str
    caption: Optional[str]
    order: int
    media_type: str
    upload_status: str
    quality_status: str
    visibility_status: str
    is_active: bool
    version: int
    upload_error: Optional[str] = None
    failure_reason: Optional[str] = None
    rejection_reason: Optional[str] = None
    original_filename: Optional[str] = None
    mime_type: str = ""
    file_size: int = 0
    local_preview_url: Optional[str] = None
    cloudinary_public_id: Optional[str] = None
    cloudinary_secure_url: Optional[str] = None
    width: Optional[int] = None
    height: Optional[int] = None
    duration_seconds: Optional[int] = None
    analyzer_score: Optional[int] = None
    analyzer_summary: Optional[str] = None
    is_deleted: bool = False
    deleted_at: Optional[datetime] = None
