from django.conf import settings

from .views import PDF_MIME_TYPE
from .views import VendorVerificationDocumentView as BaseVendorVerificationDocumentView


PDF_EOF_TAIL_BYTES = 2048
PDF_SCAN_OVERLAP_BYTES = 32
PDF_HEADER_BYTES = 4
PDF_PAGE_MARKERS = (bytes.fromhex("2f54797065202f50616765"), bytes.fromhex("2f547970652f50616765"))
PDF_PROTECTION_MARKER = bytes.fromhex("2f456e6372797074")
PDF_EOF_MARKER = bytes.fromhex("2525454f46")
PDF_HEADER_MARKER = bytes.fromhex("25504446")


class VendorVerificationDocumentView(BaseVendorVerificationDocumentView):
    """Verification document endpoint with bounded-memory PDF validation."""

    def _validate_pdf(self, uploaded_document) -> dict | None:
        max_size = int(getattr(settings, "VENDOR_VERIFICATION_DOCUMENT_MAX_SIZE_MB", 5)) * 1024 * 1024
        filename = uploaded_document.name or ""
        content_type = (getattr(uploaded_document, "content_type", "") or "").lower()
        if content_type != PDF_MIME_TYPE:
            return {"document": ["Verification documents must be uploaded as PDF files."]}
        if not filename.lower().endswith(".pdf"):
            return {"document": ["Verification document filename must end with .pdf."]}
        if uploaded_document.size > max_size:
            return {"document": [f"Verification document is too large. Maximum size is {max_size // (1024 * 1024)}MB."]}

        scan = self._scan_pdf(uploaded_document)
        if not scan["starts_with_pdf"]:
            return {"document": ["Verification document is not a valid PDF file."]}
        if not scan["has_eof_marker"]:
            return {"document": ["Verification document appears to be incomplete or corrupt."]}
        if scan["is_protected"]:
            return {"document": ["Password-protected PDFs cannot be processed."]}
        if not scan["has_page"]:
            return {"document": ["Verification document must contain at least one page."]}
        return None

    def _scan_pdf(self, uploaded_document) -> dict:
        current_position = uploaded_document.tell() if hasattr(uploaded_document, "tell") else None
        header = b""
        tail = b""
        overlap = b""
        has_page = False
        is_protected = False

        try:
            if hasattr(uploaded_document, "seek"):
                uploaded_document.seek(0)

            for chunk in uploaded_document.chunks():
                if isinstance(chunk, str):
                    chunk = chunk.encode()
                if not chunk:
                    continue

                if len(header) < PDF_HEADER_BYTES:
                    header = (header + chunk)[:PDF_HEADER_BYTES]

                scan_window = overlap + chunk
                if PDF_PROTECTION_MARKER in scan_window:
                    is_protected = True
                if any(marker in scan_window for marker in PDF_PAGE_MARKERS):
                    has_page = True

                tail = (tail + chunk)[-PDF_EOF_TAIL_BYTES:]
                overlap = scan_window[-PDF_SCAN_OVERLAP_BYTES:]
        finally:
            if hasattr(uploaded_document, "seek"):
                uploaded_document.seek(current_position or 0)

        return {
            "starts_with_pdf": header.startswith(PDF_HEADER_MARKER),
            "has_eof_marker": PDF_EOF_MARKER in tail,
            "is_protected": is_protected,
            "has_page": has_page,
        }
