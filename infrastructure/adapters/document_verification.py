from __future__ import annotations

import logging
from dataclasses import dataclass

from django.conf import settings

logger = logging.getLogger(__name__)


@dataclass(frozen=True)
class DocumentVerificationResult:
    status: str
    score: int | None = None
    summary: str | None = None


class DocumentVerificationAdapter:
    """Optional ODCR/OCR preflight adapter for verification documents."""

    UNAVAILABLE_SUMMARY = "Automated document verification is unavailable; queued for manual review."

    def verify(self, *, document_id: str, file_url: str) -> DocumentVerificationResult:
        enabled = bool(getattr(settings, "ODCR_ENABLED", False))
        api_url = getattr(settings, "ODCR_API_URL", "")
        api_key = getattr(settings, "ODCR_API_KEY", "")

        if not enabled or not api_url or not api_key:
            return DocumentVerificationResult(status="unavailable", summary=self.UNAVAILABLE_SUMMARY)

        try:
            import requests

            timeout = int(getattr(settings, "ODCR_TIMEOUT_SECONDS", 10))
            response = requests.post(
                api_url,
                json={"document_id": document_id, "file_url": file_url},
                headers={"Authorization": f"Bearer {api_key}"},
                timeout=timeout,
            )
            response.raise_for_status()
            payload = response.json()
        except Exception:
            logger.exception("Document verification preflight failed.", extra={"document_id": document_id})
            return DocumentVerificationResult(status="unavailable", summary=self.UNAVAILABLE_SUMMARY)

        status = str(payload.get("status") or "needs_manual_review")
        score = self._normalize_score(payload.get("score"))
        summary = payload.get("summary") or payload.get("message")
        return DocumentVerificationResult(status=status, score=score, summary=summary)

    def _normalize_score(self, score: object) -> int | None:
        if score is None:
            return None
        try:
            normalized = int(float(score))
        except (TypeError, ValueError):
            return None
        return max(0, min(100, normalized))
