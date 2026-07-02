from __future__ import annotations

import logging
from dataclasses import dataclass
from io import BytesIO
from urllib.request import urlopen

from django.conf import settings
from django.core.files.storage import default_storage

logger = logging.getLogger(__name__)


@dataclass(frozen=True)
class MediaQualityResult:
    status: str
    score: int | None = None
    summary: str | None = None
    width: int | None = None
    height: int | None = None
    duration_seconds: int | None = None


class MediaQualityAnalyzer:
    IMAGE_MIN_WIDTH = 800
    IMAGE_MIN_HEIGHT = 600
    VIDEO_MIN_SIZE_BYTES = 64

    def analyze(self, *, storage_path: str | None, media_type: str, file_url: str | None = None) -> MediaQualityResult:
        if media_type == "image":
            return self._analyze_image(storage_path, file_url)
        if media_type == "video":
            return self._analyze_video(storage_path, file_url)
        return MediaQualityResult(status="failed", summary="Unsupported portfolio media type.")

    def _analyze_image(self, storage_path: str | None, file_url: str | None = None) -> MediaQualityResult:
        if not storage_path and not file_url:
            return MediaQualityResult(status="needs_manual_review", summary="Image file is unavailable for automated review.")
        try:
            from PIL import Image

            if storage_path:
                with default_storage.open(storage_path, "rb") as file_obj:
                    image = Image.open(file_obj)
                    image.verify()
                    width, height = image.size
            else:
                with urlopen(file_url, timeout=10) as response:
                    content = response.read(int(getattr(settings, "VENDOR_PORTFOLIO_MAX_UPLOAD_SIZE", 4 * 1024 * 1024)) + 1)
                image = Image.open(BytesIO(content))
                image.verify()
                width, height = image.size
        except Exception:
            return MediaQualityResult(status="failed", summary="This image could not be read. Upload a clearer photo.")

        if width < self.IMAGE_MIN_WIDTH or height < self.IMAGE_MIN_HEIGHT:
            return MediaQualityResult(
                status="failed",
                score=20,
                summary="This image is too small. Upload a clearer, higher-resolution photo.",
                width=width,
                height=height,
            )
        return MediaQualityResult(
            status="passed",
            score=90,
            summary="Image quality preflight passed.",
            width=width,
            height=height,
        )

    def _analyze_video(self, storage_path: str | None, file_url: str | None = None) -> MediaQualityResult:
        if not storage_path and not file_url:
            return MediaQualityResult(status="needs_manual_review", summary="Video file is unavailable for automated review.")
        try:
            if storage_path:
                size = default_storage.size(storage_path)
                with default_storage.open(storage_path, "rb") as file_obj:
                    header = file_obj.read(32)
            else:
                with urlopen(file_url, timeout=10) as response:
                    header = response.read(32)
                    size = int(response.headers.get("Content-Length") or self.VIDEO_MIN_SIZE_BYTES)
        except Exception:
            return MediaQualityResult(status="failed", summary="This video could not be read. Upload a valid highlight video.")

        if size < self.VIDEO_MIN_SIZE_BYTES:
            return MediaQualityResult(status="failed", score=10, summary="This video could not be read. Upload a valid highlight video.")
        if b"ftyp" not in header and not header.startswith(b"\x1aE\xdf\xa3"):
            return MediaQualityResult(status="needs_manual_review", score=50, summary="Video queued for manual quality review.")
        return MediaQualityResult(status="needs_manual_review", score=70, summary="Video queued for manual quality review.")
