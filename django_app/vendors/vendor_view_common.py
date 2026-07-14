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
from application.vendors.inquiries.commands import SendInquiryCommand
from application.vendors.packages.commands import CreateServicePackageCommand, UpdateServicePackageCommand, DeactivateServicePackageCommand, ActivateServicePackageCommand
from application.vendors.portfolio.commands import AddPortfolioImageCommand, DeletePortfolioImageCommand, ReorderPortfolioImagesCommand
from application.vendors.profile.commands import CreateVendorProfileCommand, UpdateVendorProfileCommand, SubmitVendorForReviewCommand
from application.vendors.shared.commands import AuthenticatedActor, ResourceVersion
from application.vendors.inquiries.queries import ListInquiriesQuery
from application.vendors.packages.queries import ListServicePackagesQuery
from application.vendors.portfolio.queries import ListPortfolioImagesQuery
from application.vendors.profile.queries import GetVendorOnboardingStateQuery, GetVendorQuery
from application.vendors.inquiries.dtos import InquiryDTO
from application.vendors.packages.dtos import ServicePackageDTO
from application.vendors.portfolio.dtos import PortfolioImageDTO
from application.vendors.profile.dtos import VendorProfileDTO
from domain.vendors.profile.entity import VendorProfile, profile_completion_errors_for
from domain.vendors.packages.rules import PackageValidationError
from domain.vendors.shared.aggregate import ConcurrentVendorUpdate, VendorDomainError
from domain.vendors.shared.pagination import PageRequest
from infrastructure.adapters.cloudinary_adapter import CloudinaryAdapter
from .api_contracts import map_vendor_exception, resolve_expected_version, response_with_version, vendor_error_response


VENDOR_PROFILE_INCOMPLETE_CODE = "vendor_profile_incomplete"
VENDOR_PROFILE_INCOMPLETE_DETAIL = "Vendor profile setup is required before accessing this resource."
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
CREATE_VENDOR_PROFILE_ACTION = {"method": "POST", "path": "/api/django/vendors/profile/"}


def _actor(request) -> AuthenticatedActor:
    return AuthenticatedActor(user_id=request.user.id)


def _profile_dto_from_model(profile: VendorProfileModel) -> VendorProfileDTO:
    return VendorProfileDTO(
        id=profile.id,
        user_id=profile.user_id,
        business_name=profile.business_name,
        category=profile.category,
        description=profile.description,
        service_area=profile.service_area,
        contact_email=profile.contact_email,
        contact_phone=profile.contact_phone,
        custom_category=profile.custom_category,
        website=profile.website,
        profile_image_url=profile.profile_image_url,
        cover_image_url=profile.cover_image_url,
        status=profile.status,
        submitted_at=profile.submitted_at,
        approved_at=profile.approved_at,
        rejected_at=profile.rejected_at,
        rejection_reason=profile.rejection_reason,
        version=profile.version,
    )


def _profile_completion_errors(profile: object | None) -> dict[str, list[str]]:
    if profile is None:
        return {}
    if hasattr(profile, "get_profile_completion_errors"):
        return profile.get_profile_completion_errors()
    return profile_completion_errors_for(profile, VendorProfile.required_profile_fields())


def _vendor_onboarding_state(profile: object | None) -> dict:
    if profile is None:
        return {
            "profile_status": "missing",
            "can_access_dashboard": False,
            "must_complete_profile": True,
            "can_submit_for_review": False,
            "marketplace_visible": False,
            "action": dict(CREATE_VENDOR_PROFILE_ACTION),
        }

    raw_status = getattr(profile, "status", "draft") or "draft"
    status_value = str(getattr(raw_status, "value", raw_status))
    field_errors = _profile_completion_errors(profile)
    is_complete = not field_errors
    is_draft = status_value == VendorProfileModel.Status.DRAFT

    if status_value == VendorProfileModel.Status.APPROVED:
        return {
            "profile_status": status_value,
            "can_access_dashboard": True,
            "must_complete_profile": False,
            "can_submit_for_review": False,
            "marketplace_visible": True,
            "action": None,
        }
    if status_value == VendorProfileModel.Status.PENDING_REVIEW:
        return {
            "profile_status": status_value,
            "can_access_dashboard": True,
            "must_complete_profile": False,
            "can_submit_for_review": False,
            "marketplace_visible": False,
            "action": None,
        }
    if status_value == VendorProfileModel.Status.SUSPENDED:
        return {
            "profile_status": status_value,
            "can_access_dashboard": False,
            "must_complete_profile": False,
            "can_submit_for_review": False,
            "marketplace_visible": False,
            "action": None,
        }
    if status_value == VendorProfileModel.Status.REJECTED:
        return {
            "profile_status": status_value,
            "can_access_dashboard": False,
            "must_complete_profile": True,
            "can_submit_for_review": is_complete,
            "marketplace_visible": False,
            "action": None,
        }
    return {
        "profile_status": status_value,
        "can_access_dashboard": False,
        "must_complete_profile": True,
        "can_submit_for_review": is_complete,
        "marketplace_visible": False,
        "action": dict(CREATE_VENDOR_PROFILE_ACTION) if is_draft and not is_complete else None,
    }


def _get_vendor_onboarding_state(request) -> dict:
    try:
        return get_query_handlers().get_vendor_onboarding_state(GetVendorOnboardingStateQuery(actor=_actor(request)))
    except VendorDomainError:
        profile = VendorProfileModel.objects.filter(user_id=request.user.id).first()
        if profile is None:
            return _vendor_onboarding_state(None)
        return _vendor_onboarding_state(_profile_dto_from_model(profile))


def _onboarding_message(profile: object | None, onboarding: dict) -> str:
    status_value = onboarding["profile_status"]
    if status_value == "missing" or onboarding.get("action"):
        return "Complete your vendor profile before continuing."
    if status_value == VendorProfileModel.Status.APPROVED:
        return "Your vendor profile is approved and visible in the marketplace."
    if status_value == VendorProfileModel.Status.PENDING_REVIEW:
        return "Your profile is under review. Marketplace visibility starts after admin approval."
    if status_value == VendorProfileModel.Status.SUSPENDED:
        return VENDOR_SUSPENDED_DETAIL
    if status_value == VendorProfileModel.Status.REJECTED:
        return (
            getattr(profile, "rejection_reason", None)
            or "Your vendor profile needs updates before resubmission."
        )
    if onboarding.get("can_submit_for_review"):
        return "Submit your vendor profile for admin review."
    return "Complete your vendor profile before continuing."


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
    onboarding = _vendor_onboarding_state(profile)
    message = _onboarding_message(profile, onboarding)
    return Response(
        {
            "code": VENDOR_PROFILE_INCOMPLETE_CODE,
            "message": message,
            "detail": message or VENDOR_PROFILE_INCOMPLETE_DETAIL,
            "field_errors": field_errors or {},
            "onboarding": onboarding,
            "action": onboarding["action"],
        },
        status=status.HTTP_403_FORBIDDEN,
    )


def _vendor_suspended_response() -> Response:
    onboarding = _vendor_onboarding_state(type("SuspendedProfile", (), {"status": VendorProfileModel.Status.SUSPENDED})())
    return Response(
        {
            "code": VENDOR_SUSPENDED_CODE,
            "message": VENDOR_SUSPENDED_DETAIL,
            "detail": VENDOR_SUSPENDED_DETAIL,
            "onboarding": onboarding,
            "action": onboarding["action"],
        },
        status=status.HTTP_403_FORBIDDEN,
    )


def _get_current_vendor_profile(request, *, require_workspace: bool = False):
    query_handlers = get_query_handlers()
    try:
        profile = query_handlers.get_vendor_by_user(request.user.id)
    except VendorDomainError:
        model_profile = VendorProfileModel.objects.filter(user_id=request.user.id).first()
        if model_profile is None:
            raise
        profile = _profile_dto_from_model(model_profile)
    if not profile:
        onboarding = _vendor_onboarding_state(None)
        return None, Response(
            {
                "code": VENDOR_PROFILE_INCOMPLETE_CODE,
                "message": "Complete your vendor profile before continuing.",
                "detail": "No vendor profile found.",
                "field_errors": {},
                "onboarding": onboarding,
                "action": onboarding["action"],
            },
            status=status.HTTP_404_NOT_FOUND,
        )
    completion_errors = _profile_completion_errors(profile)
    if require_workspace:
        if profile.status == VendorProfileModel.Status.SUSPENDED:
            return None, _vendor_suspended_response()
        if profile.status in {VendorProfileModel.Status.DRAFT, VendorProfileModel.Status.REJECTED} or completion_errors:
            return None, _vendor_profile_incomplete_response(profile, completion_errors)
    return profile, None


def _serialize_profile(dto: VendorProfileDTO, *, message: str | None = None) -> dict:
    onboarding = _vendor_onboarding_state(dto)
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
        "message": message or _onboarding_message(dto, onboarding),
    }
    return payload


def _validation_error_response(errors, *, profile: VendorProfileDTO | None = None) -> Response:
    field_errors = {
        key: [str(message) for message in value]
        for key, value in dict(errors).items()
    }
    onboarding = _vendor_onboarding_state(profile)
    return Response(
        {
            "code": VENDOR_PROFILE_INCOMPLETE_CODE,
            "message": "Please fix the highlighted profile fields.",
            "field_errors": field_errors,
            "onboarding": onboarding,
            "action": onboarding["action"],
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


def _message_from_response(response: Response, fallback: str) -> str:
    data = response.data if isinstance(response.data, dict) else {}
    return str(data.get("message") or data.get("detail") or fallback)


def _add_success_contract(response: Response, *, code: str, message: str) -> Response:
    if isinstance(response.data, dict):
        response.data.setdefault("success", True)
        response.data.setdefault("code", code)
        response.data.setdefault("message", message)
    return response


def _add_error_contract(response: Response, *, code: str, message: str) -> Response:
    if not isinstance(response.data, dict):
        return response

    field_errors = response.data.get("field_errors")
    if field_errors is None:
        field_errors = {
            key: value
            for key, value in response.data.items()
            if isinstance(value, list)
        }

    response.data.setdefault("success", False)
    response.data.setdefault("code", code)
    response.data.setdefault("message", _message_from_response(response, message))
    response.data.setdefault("detail", response.data["message"])
    response.data.setdefault("field_errors", field_errors or {})
    return response


def _normalize_response_contract(
    response: Response,
    *,
    success_code: str,
    success_message: str,
    error_code: str,
    error_message: str,
) -> Response:
    if response.status_code >= status.HTTP_400_BAD_REQUEST:
        return _add_error_contract(response, code=error_code, message=error_message)
    return _add_success_contract(response, code=success_code, message=success_message)


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
