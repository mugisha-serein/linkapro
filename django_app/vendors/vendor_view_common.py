import logging
import uuid
import httpx
from pathlib import Path
from rest_framework.views import APIView
from rest_framework.response import Response
from rest_framework import status
from rest_framework.exceptions import ValidationError as DRFValidationError
from rest_framework.permissions import AllowAny, IsAuthenticated
from django.conf import settings
from django.db import IntegrityError, transaction
from django.db.models import Max, Prefetch
from django.utils.decorators import method_decorator
from django.views.decorators.csrf import csrf_exempt
from django_app.common.permissions import IsVendor, IsAdmin
from django_app.common.api_responses import api_error, api_success
from rest_framework.parsers import MultiPartParser, FormParser, JSONParser

from .serializers import (
    VendorProfileSerializer,
    PortfolioImageSerializer,
    ServicePackageSerializer,
    InquirySerializer,
    SubmitForReviewSerializer,
    ReorderImagesSerializer,
    VerificationDocumentUploadSerializer,
    VendorPublicProfileSerializer,
)
from .models import PortfolioImage as PortfolioImageModel
from .models import VerificationDocument
from .models import VendorProfile as VendorProfileModel
from .models import ServicePackage as ServicePackageModel
from .throttles import PublicVendorInquiryThrottle
from .services import get_command_handlers, get_query_handlers
from application.vendors.commands import (
    AuthenticatedActor,
    CreateVendorProfileCommand,
    UpdateVendorProfileCommand,
    SubmitVendorForReviewCommand,
    AddPortfolioImageCommand,
    DeletePortfolioImageCommand,
    ReorderPortfolioImagesCommand,
    CreateServicePackageCommand,
    UpdateServicePackageCommand,
    DeactivateServicePackageCommand,
    ActivateServicePackageCommand,
    SendInquiryCommand,
    ResourceVersion,
)
from application.vendors.queries import (
    GetVendorQuery,
    ListInquiriesQuery,
    ListPortfolioImagesQuery,
    ListServicePackagesQuery,
)
from application.vendors.dtos import (
    VendorProfileDTO,
    PortfolioImageDTO,
    ServicePackageDTO,
    InquiryDTO,
)
from application.vendors.profile.onboarding_policy import (
    SETUP_ROUTE,
    build_vendor_onboarding_contract,
    vendor_field_errors,
)
from domain.vendors.packages.rules import PackageValidationError
from domain.vendors.shared.aggregate import ConcurrentVendorUpdate, VendorDomainError
from domain.vendors.shared.pagination import PageRequest
from infrastructure.adapters.cloudinary_adapter import CloudinaryAdapter
from .api_contracts import map_vendor_exception, resolve_expected_version, response_with_version, vendor_error_response


VENDOR_PROFILE_INCOMPLETE_CODE = "vendor_profile_incomplete"
VENDOR_PROFILE_INCOMPLETE_DETAIL = "Vendor profile setup is required before accessing this resource."
VENDOR_PROFILE_SETUP_REDIRECT = SETUP_ROUTE
VENDOR_SUSPENDED_CODE = "vendor_suspended"
VENDOR_SUSPENDED_DETAIL = "Your vendor account is suspended. Please contact support."
ALLOWED_PORTFOLIO_IMAGE_TYPES = {"image/jpeg", "image/png", "image/webp"}
ALLOWED_PORTFOLIO_VIDEO_TYPES = {"video/mp4", "video/webm", "video/quicktime"}
ALLOWED_PORTFOLIO_MEDIA_TYPES = ALLOWED_PORTFOLIO_IMAGE_TYPES | ALLOWED_PORTFOLIO_VIDEO_TYPES
ALLOWED_VENDOR_BRANDING_IMAGE_TYPES = {"image/jpeg", "image/png", "image/webp"}
VIDEO_PORTFOLIO_MAX_UPLOAD_SIZE = 10 * 1024 * 1024
PDF_MIME_TYPE = "application/pdf"
DOCUMENT_RECEIVED_MESSAGE = "Document received. Verification will continue automatically."
logger = logging.getLogger(__name__)
PORTFOLIO_MEDIA_INVALID_CODE = "portfolio_media_invalid"
PORTFOLIO_MEDIA_INVALID_MESSAGE = "Upload a valid portfolio image or highlight video."
VENDOR_PROFILE_IMAGE_INVALID_CODE = "vendor_profile_image_invalid"
VENDOR_COVER_IMAGE_INVALID_CODE = "vendor_cover_image_invalid"
VENDOR_PROFILE_MEDIA_UPLOAD_FAILED_CODE = "vendor_profile_media_upload_failed"
VENDOR_PACKAGE_INTEGRITY_CODE = "vendor_package_integrity_error"
VENDOR_PACKAGE_PAGINATION_CODE = "vendor_package_pagination_invalid"


def _actor(request) -> AuthenticatedActor:
    return AuthenticatedActor(user_id=request.user.id)


def _get_public_marketplace_stats(vendor_id) -> dict:
    settings_module = getattr(settings, "SETTINGS_MODULE", "")
    base_url = (getattr(settings, "FASTAPI_INTERNAL_URL", None) or "").strip().rstrip("/")
    if not base_url or settings_module.endswith(".test"):
        return {"average_rating": 0, "total_reviews": 0}
    try:
        response = httpx.get(f"{base_url}/marketplace/vendors/{vendor_id}", timeout=3)
        response.raise_for_status()
        payload = response.json()
        return {
            "average_rating": payload.get("average_rating", 0),
            "total_reviews": payload.get("total_reviews", 0),
        }
    except (httpx.HTTPError, ValueError, TypeError):
        logger.warning("Public marketplace rating summary unavailable.", extra={"vendor_id": str(vendor_id)})
        return {"average_rating": 0, "total_reviews": 0}


def _vendor_profile_incomplete_response(
    profile: VendorProfileDTO | None = None,
    field_errors: dict[str, list[str]] | None = None,
) -> Response:
    onboarding = build_vendor_onboarding_contract(profile)
    return Response(
        {
            "code": VENDOR_PROFILE_INCOMPLETE_CODE,
            "message": onboarding["message"],
            "detail": onboarding["message"] or VENDOR_PROFILE_INCOMPLETE_DETAIL,
            "redirect_to": onboarding["redirect_to"],
            "field_errors": field_errors or {},
            "onboarding": onboarding,
        },
        status=status.HTTP_403_FORBIDDEN,
    )


def _vendor_suspended_response() -> Response:
    onboarding = build_vendor_onboarding_contract(type("SuspendedProfile", (), {"status": VendorProfileModel.Status.SUSPENDED})())
    return Response(
        {
            "code": VENDOR_SUSPENDED_CODE,
            "message": VENDOR_SUSPENDED_DETAIL,
            "detail": VENDOR_SUSPENDED_DETAIL,
            "redirect_to": onboarding["redirect_to"],
            "onboarding": onboarding,
        },
        status=status.HTTP_403_FORBIDDEN,
    )


def _get_current_vendor_profile(request, *, require_workspace: bool = False):
    query_handlers = get_query_handlers()
    profile = query_handlers.get_vendor_by_user(request.user.id)
    if not profile:
        return None, Response(
            {
                "code": VENDOR_PROFILE_INCOMPLETE_CODE,
                "message": "Complete your vendor profile before continuing.",
                "detail": "No vendor profile found.",
                "redirect_to": VENDOR_PROFILE_SETUP_REDIRECT,
                "field_errors": {},
                "onboarding": build_vendor_onboarding_contract(None),
            },
            status=status.HTTP_404_NOT_FOUND,
        )
    completion_errors = vendor_field_errors(profile)
    if require_workspace:
        if profile.status == VendorProfileModel.Status.SUSPENDED:
            return None, _vendor_suspended_response()
        if profile.status in {VendorProfileModel.Status.DRAFT, VendorProfileModel.Status.REJECTED} or completion_errors:
            return None, _vendor_profile_incomplete_response(profile, completion_errors)
    return profile, None


def _serialize_profile(dto: VendorProfileDTO, *, message: str | None = None) -> dict:
    onboarding = build_vendor_onboarding_contract(dto)
    payload = {
        "id": str(dto.id),
        "user_id": str(dto.user_id),
        "business_name": dto.business_name,
        "category": dto.category,
        "custom_category": dto.custom_category,
        "description": dto.description,
        "service_area": dto.service_area,
        "contact_email": dto.contact_email,
        "contact_phone": dto.contact_phone,
        "website": dto.website,
        "profile_image_url": dto.profile_image_url,
        "cover_image_url": dto.cover_image_url,
        "status": dto.status,
        "submitted_at": dto.submitted_at.isoformat() if dto.submitted_at else None,
        "approved_at": dto.approved_at.isoformat() if dto.approved_at else None,
        "rejected_at": dto.rejected_at.isoformat() if dto.rejected_at else None,
        "rejection_reason": dto.rejection_reason,
        "version": dto.version,
        "onboarding": onboarding,
        "message": message or onboarding["message"],
    }
    return payload


def _validation_error_response(errors, *, profile: VendorProfileDTO | None = None) -> Response:
    field_errors = {
        key: [str(message) for message in value]
        for key, value in dict(errors).items()
    }
    onboarding = build_vendor_onboarding_contract(profile)
    return Response(
        {
            "code": VENDOR_PROFILE_INCOMPLETE_CODE,
            "message": "Please fix the highlighted profile fields.",
            "field_errors": field_errors,
            "redirect_to": onboarding["redirect_to"],
            "onboarding": onboarding,
        },
        status=status.HTTP_400_BAD_REQUEST,
    )


def _stable_package_integrity_response(exc: Exception, *, status_code=status.HTTP_409_CONFLICT) -> Response:
    field_errors = getattr(exc, "field_errors", {}) or {}
    code = getattr(exc, "code", VENDOR_PACKAGE_INTEGRITY_CODE)
    return Response(
        {
            "code": code,
            "message": "Service package could not be saved.",
            "detail": "Service package could not be saved.",
            "field_errors": field_errors,
        },
        status=status_code,
    )


def _page_request_from_query(request) -> tuple[PageRequest | None, Response | None]:
    try:
        limit = int(request.query_params.get("limit", "50"))
        offset = int(request.query_params.get("offset", "0"))
        return PageRequest(limit=limit, offset=offset), None
    except (TypeError, ValueError):
        return None, Response(
            {
                "code": VENDOR_PACKAGE_PAGINATION_CODE,
                "message": "Package pagination parameters are invalid.",
                "detail": "Use integer limit 1-100 and offset 0-10000.",
                "field_errors": {"pagination": ["Use integer limit 1-100 and offset 0-10000."]},
            },
            status=status.HTTP_400_BAD_REQUEST,
        )


def _has_submitted_verification_document(vendor_id) -> bool:
    return VerificationDocument.objects.filter(vendor_id=vendor_id).exclude(
        upload_status=VerificationDocument.UploadStatus.FAILED,
    ).exclude(
        verification_status__in=[
            VerificationDocument.VerificationStatus.FAILED,
            VerificationDocument.VerificationStatus.REJECTED,
        ],
    ).exists()


def _portfolio_media_error(message: str, *, status_code=status.HTTP_400_BAD_REQUEST) -> Response:
    return Response(
        {
            "code": PORTFOLIO_MEDIA_INVALID_CODE,
            "message": PORTFOLIO_MEDIA_INVALID_MESSAGE,
            "field_errors": {"media": [message]},
        },
        status=status_code,
    )


def _log_portfolio_validation_failure(request, profile, uploaded_media, message: str) -> None:
    filename = getattr(uploaded_media, "name", "") or ""
    logger.warning(
        "Portfolio media upload rejected.",
        extra={
            "user_id": str(getattr(request.user, "id", "")),
            "vendor_id": str(getattr(profile, "id", "")) if profile else None,
            "upload_filename": filename,
            "upload_content_type": (getattr(uploaded_media, "content_type", "") or "").lower() if uploaded_media else None,
            "upload_file_size": getattr(uploaded_media, "size", None),
            "upload_extension": Path(filename).suffix.lower(),
            "validation_code": PORTFOLIO_MEDIA_INVALID_CODE,
            "validation_message": message,
        },
    )


def _safe_portfolio_display_url(*urls: str | None) -> str | None:
    for url in urls:
        if not url:
            continue
        if _is_private_portfolio_upload_url(url):
            continue
        return url
    return None


def _is_private_portfolio_upload_url(url: str) -> bool:
    return "vendor_portfolio_uploads" in url or url.startswith("/media/")


def _safe_public_branding_url(url: str | None) -> str | None:
    if not url:
        return None
    value = str(url).strip()
    if not value or not value.startswith("https://"):
        return None
    if value.startswith("/media/") or "vendor_portfolio_uploads" in value:
        return None
    return value


def _infer_image_content_type(extension: str, header: bytes) -> str | None:
    if extension in {".jpg", ".jpeg"} and header.startswith(b"\xff\xd8\xff"):
        return "image/jpeg"
    if extension == ".png" and header.startswith(b"\x89PNG\r\n\x1a\n"):
        return "image/png"
    if extension == ".webp" and header.startswith(b"RIFF") and header[8:12] == b"WEBP":
        return "image/webp"
    return None


def _branding_media_error(kind: str, message: str, *, status_code=status.HTTP_400_BAD_REQUEST) -> Response:
    is_cover = kind == "cover"
    return Response(
        {
            "code": VENDOR_COVER_IMAGE_INVALID_CODE if is_cover else VENDOR_PROFILE_IMAGE_INVALID_CODE,
            "message": "Upload a valid vendor cover image." if is_cover else "Upload a valid vendor profile image.",
            "detail": message,
            "field_errors": {"image": [message]},
        },
        status=status_code,
    )


__all__ = [name for name in globals() if not name.startswith("__")]
