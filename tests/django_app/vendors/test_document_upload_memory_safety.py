import pytest
from django.urls import resolve, reverse

from django_app.vendors.views.profile import VendorVerificationDocumentView


class ChunkOnlyUpload:
    def __init__(self, chunks, *, name="document.pdf", content_type="application/pdf"):
        self._chunks = list(chunks)
        self.name = name
        self.content_type = content_type
        self.size = sum(len(chunk) for chunk in self._chunks)
        self.position = 0
        self.read_called = False
        self.chunks_called = False
        self.seek_calls = []

    def chunks(self):
        self.chunks_called = True
        yield from self._chunks

    def read(self, *args, **kwargs):
        self.read_called = True
        raise AssertionError("full-file read must not be used during PDF validation")

    def tell(self):
        return self.position

    def seek(self, position):
        self.position = position
        self.seek_calls.append(position)


def test_verification_document_route_uses_streaming_view():
    resolved = resolve(reverse("vendor-verification-documents"))

    assert resolved.func.cls is VendorVerificationDocumentView


def test_pdf_validation_uses_chunks_without_full_file_read():
    upload = ChunkOnlyUpload([
        b"%PDF-1.7\n",
        b"1 0 obj << /Type /Page >> endobj\n",
        b"trailer\n%%EOF\n",
    ])

    error = VendorVerificationDocumentView()._validate_pdf(upload)

    assert error is None
    assert upload.chunks_called is True
    assert upload.read_called is False
    assert upload.seek_calls[0] == 0
    assert upload.seek_calls[-1] == 0


def test_pdf_validation_detects_missing_eof_from_streamed_tail():
    upload = ChunkOnlyUpload([
        b"%PDF-1.7\n",
        b"1 0 obj << /Type /Page >> endobj\n",
    ])

    error = VendorVerificationDocumentView()._validate_pdf(upload)

    assert error == {"document": ["Verification document appears to be incomplete or corrupt."]}
    assert upload.read_called is False


def test_pdf_validation_detects_protected_marker_across_chunks():
    upload = ChunkOnlyUpload([
        b"%PDF-1.7\n1 0 obj << /Type /Page >>\n",
        b"/Enc",
        b"rypt 2 0 R\n%%EOF\n",
    ])

    error = VendorVerificationDocumentView()._validate_pdf(upload)

    assert error == {"document": ["Password-protected PDFs cannot be processed."]}
    assert upload.read_called is False


def test_pdf_validation_detects_page_marker_across_chunks():
    upload = ChunkOnlyUpload([
        b"%PDF-1.7\n1 0 obj << /Ty",
        b"pe /Page >> endobj\n%%EOF\n",
    ])

    error = VendorVerificationDocumentView()._validate_pdf(upload)

    assert error is None
    assert upload.read_called is False
