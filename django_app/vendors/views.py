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
from django.db import transaction
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
    CreateVendorProfileCommand,
    UpdateVendorProfileCommand,
    SubmitVendorForReviewCommand,
    DeletePortfolioImageCommand,
    ReorderPortfolioImagesCommand,
    CreateServicePackageCommand,
    UpdateServicePackageCommand,
    DeactivateServicePackageCommand,
    SendInquiryCommand,
)
from application.vendors.dtos import (
    VendorProfileDTO,
    PortfolioImageDTO,
    ServicePackageDTO,
    InquiryDTO,
)
from application.vendors.onboarding_policy import (
    SETUP_ROUTE,
    build_vendor_onboarding_contract,
    vendor_field_errors,
)
from domain.vendors.package_rules import PackageValidationError
from infrastructure.adapters.cloudinary_adapter import CloudinaryAdapter


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


@method_decorator(csrf_exempt, name="dispatch")
class VendorProfileView(APIView):
    permission_classes = [IsAuthenticated, IsVendor]

    def get(self, request):
        """Get the current user's vendor profile."""
        profile, error_response = _get_current_vendor_profile(request)
        if error_response:
            return error_response
        return Response(_serialize_profile(profile))

    def post(self, request):
        """Create a new vendor profile for the current user."""
        serializer = VendorProfileSerializer(data=request.data)
        if not serializer.is_valid():
            return _validation_error_response(serializer.errors)
        data = serializer.validated_data

        cmd = CreateVendorProfileCommand(
            user_id=request.user.id,
            business_name=data["business_name"],
            category=data["category"],
            description=data["description"],
            service_area=data["service_area"],
            contact_email=data["contact_email"],
            contact_phone=data["contact_phone"],
            custom_category=data.get("custom_category"),
            website=data.get("website"),
        )

        try:
            command_handlers = get_command_handlers()
            profile = command_handlers.create_profile(cmd)
            return Response(
                _serialize_profile(profile, message="Vendor profile saved."),
                status=status.HTTP_201_CREATED,
            )
        except ValueError as e:
            return Response(
                {
                    "code": "vendor_profile_save_failed",
                    "message": str(e),
                    "detail": str(e),
                    "field_errors": {},
                    "redirect_to": VENDOR_PROFILE_SETUP_REDIRECT,
                    "onboarding": build_vendor_onboarding_contract(None),
                },
                status=status.HTTP_400_BAD_REQUEST,
            )

    def patch(self, request):
        """Update the current user's vendor profile."""
        profile, error_response = _get_current_vendor_profile(request)
        if error_response:
            return error_response

        serializer = VendorProfileSerializer(data=request.data, partial=True)
        if not serializer.is_valid():
            return _validation_error_response(serializer.errors, profile=profile)
        data = serializer.validated_data

        cmd = UpdateVendorProfileCommand(
            vendor_id=profile.id,
            business_name=data.get("business_name"),
            category=data.get("category"),
            description=data.get("description"),
            service_area=data.get("service_area"),
            contact_email=data.get("contact_email"),
            contact_phone=data.get("contact_phone"),
            custom_category=data.get("custom_category"),
            website=data.get("website"),
        )

        try:
            command_handlers = get_command_handlers()
            updated_profile = command_handlers.update_profile(cmd)
            return Response(_serialize_profile(updated_profile, message="Vendor profile saved."))
        except ValueError as e:
            return Response(
                {
                    "code": "vendor_profile_save_failed",
                    "message": str(e),
                    "detail": str(e),
                    "field_errors": {},
                    "redirect_to": build_vendor_onboarding_contract(profile)["redirect_to"],
                    "onboarding": build_vendor_onboarding_contract(profile),
                },
                status=status.HTTP_400_BAD_REQUEST,
            )


class VendorBrandingMediaView(APIView):
    permission_classes = [IsAuthenticated, IsVendor]
    parser_classes = [MultiPartParser, FormParser]

    media_kind = "profile"
    folder = "vendor_profile_images"
    min_width = 300
    min_height = 300
    max_upload_size = 2 * 1024 * 1024

    def post(self, request):
        profile, error_response = _get_current_vendor_profile(request)
        if error_response:
            return error_response

        uploaded_media = request.FILES.get("image") or request.FILES.get("media")
        if not uploaded_media:
            return _branding_media_error(self.media_kind, "No image file provided.")

        validation_error = self._validate_branding_image(uploaded_media)
        if validation_error:
            return validation_error

        if hasattr(uploaded_media, "seek"):
            uploaded_media.seek(0)
        try:
            upload_result = CloudinaryAdapter().upload_image(
                uploaded_media,
                folder=self.folder,
                fallback_to_storage=False,
            )
        except Exception:
            logger.exception(
                "Vendor branding media upload failed.",
                extra={"vendor_id": str(profile.id), "media_kind": self.media_kind},
            )
            return Response(
                {
                    "code": VENDOR_PROFILE_MEDIA_UPLOAD_FAILED_CODE,
                    "message": "Vendor profile media upload failed.",
                    "detail": "Upload failed. Please try again.",
                    "field_errors": {"image": ["Upload failed. Please try again."]},
                },
                status=status.HTTP_502_BAD_GATEWAY,
            )

        secure_url = _safe_public_branding_url(upload_result.get("secure_url"))
        if not secure_url:
            return Response(
                {
                    "code": VENDOR_PROFILE_MEDIA_UPLOAD_FAILED_CODE,
                    "message": "Vendor profile media upload failed.",
                    "detail": "Upload did not return a safe public image URL.",
                    "field_errors": {"image": ["Upload did not return a safe public image URL."]},
                },
                status=status.HTTP_502_BAD_GATEWAY,
            )

        vendor = VendorProfileModel.objects.get(id=profile.id, user_id=request.user.id)
        if self.media_kind == "cover":
            vendor.cover_image_url = secure_url
            vendor.cover_image_public_id = upload_result.get("public_id")
            update_fields = ["cover_image_url", "cover_image_public_id", "updated_at"]
        else:
            vendor.profile_image_url = secure_url
            vendor.profile_image_public_id = upload_result.get("public_id")
            update_fields = ["profile_image_url", "profile_image_public_id", "updated_at"]
        vendor.save(update_fields=update_fields)
        if self.media_kind == "cover":
            self._enqueue_projection_update(vendor)

        updated_profile = get_query_handlers().get_vendor(vendor.id)
        return Response(_serialize_profile(updated_profile, message="Vendor profile media saved."))

    def delete(self, request):
        profile, error_response = _get_current_vendor_profile(request)
        if error_response:
            return error_response

        vendor = VendorProfileModel.objects.get(id=profile.id, user_id=request.user.id)
        public_id = vendor.cover_image_public_id if self.media_kind == "cover" else vendor.profile_image_public_id
        self._delete_cloudinary_image(public_id)
        if self.media_kind == "cover":
            vendor.cover_image_url = None
            vendor.cover_image_public_id = None
            update_fields = ["cover_image_url", "cover_image_public_id", "updated_at"]
        else:
            vendor.profile_image_url = None
            vendor.profile_image_public_id = None
            update_fields = ["profile_image_url", "profile_image_public_id", "updated_at"]
        vendor.save(update_fields=update_fields)
        if self.media_kind == "cover":
            self._enqueue_projection_update(vendor)

        updated_profile = get_query_handlers().get_vendor(vendor.id)
        return Response(_serialize_profile(updated_profile, message="Vendor profile media removed."))

    def _validate_branding_image(self, uploaded_media) -> Response | None:
        content_type = (getattr(uploaded_media, "content_type", "") or "").lower()
        filename = uploaded_media.name or ""
        extension = Path(filename).suffix.lower()
        if extension not in {".jpg", ".jpeg", ".png", ".webp"}:
            return _branding_media_error(self.media_kind, "Only JPEG, PNG, or WEBP image files are allowed.")
        if uploaded_media.size > self.max_upload_size:
            size_mb = self.max_upload_size // (1024 * 1024)
            return _branding_media_error(self.media_kind, f"Image file is too large. Maximum size is {size_mb}MB.")

        current_position = uploaded_media.tell() if hasattr(uploaded_media, "tell") else None
        try:
            uploaded_media.seek(0)
            header = uploaded_media.read(128)
        finally:
            try:
                uploaded_media.seek(current_position or 0)
            except Exception:
                pass
        inferred_type = _infer_image_content_type(extension, header)
        if content_type not in ALLOWED_VENDOR_BRANDING_IMAGE_TYPES or inferred_type != content_type:
            return _branding_media_error(self.media_kind, "Image type does not match the uploaded file.")

        dimensions = self._image_dimensions(uploaded_media)
        if dimensions is None:
            return _branding_media_error(self.media_kind, "This image could not be read. Upload a valid image.")
        width, height = dimensions
        if width < self.min_width or height < self.min_height:
            return _branding_media_error(
                self.media_kind,
                f"Image is too small. Minimum size is {self.min_width}x{self.min_height}px.",
            )
        if self.media_kind == "cover" and width <= height:
            return _branding_media_error(self.media_kind, "Cover image must use a landscape orientation.")
        return None

    def _image_dimensions(self, uploaded_media) -> tuple[int, int] | None:
        current_position = uploaded_media.tell() if hasattr(uploaded_media, "tell") else None
        try:
            from PIL import Image

            uploaded_media.seek(0)
            with Image.open(uploaded_media) as image:
                image.verify()
            uploaded_media.seek(0)
            with Image.open(uploaded_media) as image:
                return image.size
        except Exception:
            return None
        finally:
            try:
                uploaded_media.seek(current_position or 0)
            except Exception:
                pass

    def _delete_cloudinary_image(self, public_id: str | None) -> None:
        if not public_id:
            return
        try:
            CloudinaryAdapter().delete_image(public_id)
        except Exception:
            logger.warning("Vendor branding Cloudinary delete failed.", extra={"public_id": public_id}, exc_info=True)

    def _enqueue_projection_update(self, vendor: VendorProfileModel) -> None:
        def enqueue():
            from django_app.governance.marketplace_outbox import enqueue_vendor_projection

            enqueue_vendor_projection(vendor, reason="vendor_cover_image_updated")

        transaction.on_commit(enqueue)


class VendorCoverImageView(VendorBrandingMediaView):
    media_kind = "cover"
    folder = "vendor_cover_images"
    min_width = 1200
    min_height = 500
    max_upload_size = 4 * 1024 * 1024


class VendorProfileStatusView(APIView):
    permission_classes = [IsAuthenticated, IsVendor]

    def get(self, request):
        profile, error_response = _get_current_vendor_profile(request)
        if error_response and profile is None:
            return Response(
                {
                    "profile": None,
                    "onboarding": build_vendor_onboarding_contract(None),
                }
            )
        return Response(
            {
                "profile": _serialize_profile(profile) if profile else None,
                "onboarding": build_vendor_onboarding_contract(profile),
            }
        )


class VendorSubmitForReviewView(APIView):
    permission_classes = [IsAuthenticated, IsVendor]

    def post(self, request):
        """Submit the vendor profile for admin review."""
        profile, error_response = _get_current_vendor_profile(request)
        if error_response:
            return error_response

        completion_errors = vendor_field_errors(profile)
        if completion_errors:
            return _vendor_profile_incomplete_response(profile, completion_errors)

        if not _has_submitted_verification_document(profile.id):
            onboarding = build_vendor_onboarding_contract(profile)
            return Response(
                {
                    "code": "vendor_verification_document_required",
                    "message": "Upload a verification PDF before submitting your profile for review.",
                    "field_errors": {"document": ["Upload a verification PDF before submitting your profile for review."]},
                    "redirect_to": onboarding["redirect_to"],
                    "onboarding": onboarding,
                },
                status=status.HTTP_400_BAD_REQUEST,
            )

        cmd = SubmitVendorForReviewCommand(vendor_id=profile.id)
        try:
            command_handlers = get_command_handlers()
            updated_profile = command_handlers.submit_for_review(cmd)
            return Response(_serialize_profile(updated_profile, message="Profile submitted for review."))
        except ValueError as e:
            onboarding = build_vendor_onboarding_contract(profile)
            return Response(
                {
                    "code": "vendor_submit_failed",
                    "message": str(e),
                    "field_errors": {},
                    "redirect_to": onboarding["redirect_to"],
                    "onboarding": onboarding,
                },
                status=status.HTTP_400_BAD_REQUEST,
            )


class PortfolioImageView(APIView):
    permission_classes = [IsAuthenticated, IsVendor]
    parser_classes = [MultiPartParser, FormParser, JSONParser]

    def get(self, request):
        """List portfolio images for the current vendor."""
        profile, error_response = _get_current_vendor_profile(request, require_workspace=True)
        if error_response:
            return error_response
        query_handlers = get_query_handlers()

        images = query_handlers.list_portfolio_images(profile.id)
        return Response([self._serialize_image(img) for img in images])

    def post(self, request):
        """Upload a new portfolio image/video (via Celery task)."""
        profile, error_response = _get_current_vendor_profile(request)
        if error_response:
            if getattr(error_response, "status_code", None) == status.HTTP_404_NOT_FOUND:
                return _portfolio_media_error(
                    "Complete your vendor profile before uploading portfolio media.",
                    status_code=status.HTTP_400_BAD_REQUEST,
                )
            return error_response
        if profile.status in {VendorProfileModel.Status.REJECTED, VendorProfileModel.Status.SUSPENDED}:
            onboarding = build_vendor_onboarding_contract(profile)
            return Response(
                {
                    "code": VENDOR_SUSPENDED_CODE if profile.status == VendorProfileModel.Status.SUSPENDED else VENDOR_PROFILE_INCOMPLETE_CODE,
                    "message": onboarding["message"],
                    "field_errors": {"media": [onboarding["message"]]},
                    "redirect_to": onboarding["redirect_to"],
                    "onboarding": onboarding,
                },
                status=status.HTTP_403_FORBIDDEN,
            )

        uploaded_media = request.FILES.get("media") or request.FILES.get("image")
        if not uploaded_media:
            return _portfolio_media_error("No portfolio media file provided.")

        validation_error, media_type, dimensions = self._validate_portfolio_media(uploaded_media)
        if validation_error:
            message = validation_error["field_errors"]["media"][0]
            _log_portfolio_validation_failure(request, profile, uploaded_media, message)
            return Response(validation_error, status=status.HTTP_400_BAD_REQUEST)

        serializer = PortfolioImageSerializer(data={"caption": request.data.get("caption", "")})
        serializer.is_valid(raise_exception=True)

        image_id = uuid.uuid4()
        shared_upload = self._upload_portfolio_media(uploaded_media, media_type, str(image_id))
        max_order = PortfolioImageModel.objects.filter(vendor_id=profile.id).aggregate(Max("order"))["order__max"]
        image = PortfolioImageModel.objects.create(
            id=image_id,
            vendor_id=profile.id,
            public_id=shared_upload["public_id"],
            secure_url=shared_upload["secure_url"],
            caption=serializer.validated_data.get("caption") or None,
            order=(max_order if max_order is not None else -1) + 1,
            media_type=media_type,
            is_active=True,
            upload_status=PortfolioImageModel.UploadStatus.QUEUED,
            quality_status=PortfolioImageModel.QualityStatus.PENDING_ANALYSIS,
            visibility_status=PortfolioImageModel.VisibilityStatus.PRIVATE,
            original_filename=uploaded_media.name,
            mime_type=(getattr(uploaded_media, "content_type", "") or "").lower(),
            file_size=uploaded_media.size,
            width=dimensions.get("width"),
            height=dimensions.get("height"),
            local_preview_url=None,
            temp_upload_path=None,
            cloudinary_public_id=shared_upload["public_id"],
            cloudinary_secure_url=shared_upload["secure_url"],
        )

        from tasks.image_tasks import process_vendor_portfolio_media_task

        processing_deferred = False
        try:
            process_vendor_portfolio_media_task.delay(str(image.id))
        except Exception:
            processing_deferred = True
            image.upload_status = PortfolioImageModel.UploadStatus.PROCESSING_DEFERRED
            image.save(update_fields=["upload_status", "updated_at"])
            logger.exception("Vendor portfolio media dispatch deferred.", extra={"image_id": str(image.id)})
        return Response(
            {
                "status": "queued",
                "job_id": str(image.id),
                "processing_deferred": processing_deferred,
                "message": "Portfolio item received. Review will continue automatically.",
                "item": self._serialize_model_image(image),
            },
            status=status.HTTP_202_ACCEPTED,
        )

    def delete(self, request, image_id):
        """Delete a portfolio image."""
        profile, error_response = _get_current_vendor_profile(request, require_workspace=True)
        if error_response:
            return error_response
        query_handlers = get_query_handlers()

        # Verify ownership: fetch the image and check vendor_id
        images = query_handlers.list_portfolio_images(profile.id)
        image = next((img for img in images if img.id == image_id), None)
        if not image:
            return Response(
                {"detail": "Image not found or does not belong to this vendor."},
                status=status.HTTP_404_NOT_FOUND
            )

        cmd = DeletePortfolioImageCommand(image_id=image_id, deleted_by_id=request.user.id)
        command_handlers = get_command_handlers()
        command_handlers.delete_portfolio_image(cmd)
        return Response(
            {
                "message": "Portfolio item removed from active listings.",
                "id": str(image_id),
            },
            status=status.HTTP_200_OK,
        )

    def _serialize_image(self, dto: PortfolioImageDTO) -> dict:
        return {
            "id": str(dto.id),
            "secure_url": _safe_portfolio_display_url(dto.cloudinary_secure_url, dto.secure_url),
            "local_preview_url": None,
            "display_url": _safe_portfolio_display_url(dto.cloudinary_secure_url, dto.secure_url),
            "media_type": dto.media_type,
            "caption": dto.caption,
            "order": dto.order,
            "upload_status": dto.upload_status,
            "quality_status": dto.quality_status,
            "visibility_status": dto.visibility_status,
            "upload_error": dto.upload_error,
            "failure_reason": dto.failure_reason,
            "rejection_reason": dto.rejection_reason,
            "original_filename": dto.original_filename,
            "mime_type": dto.mime_type,
            "file_size": dto.file_size,
            "cloudinary_secure_url": _safe_portfolio_display_url(dto.cloudinary_secure_url),
            "width": dto.width,
            "height": dto.height,
            "duration_seconds": dto.duration_seconds,
            "analyzer_score": dto.analyzer_score,
            "analyzer_summary": dto.analyzer_summary,
            "is_active": dto.is_active,
            "is_deleted": dto.is_deleted,
        }

    def _upload_portfolio_media(self, uploaded_media, media_type: str, media_id: str) -> dict:
        if hasattr(uploaded_media, "seek"):
            uploaded_media.seek(0)
        adapter = CloudinaryAdapter()
        if media_type == PortfolioImageModel.MediaType.IMAGE:
            return adapter.upload_image(uploaded_media, fallback_to_storage=False)
        return adapter.upload_file(
            uploaded_media,
            folder="vendor_portfolio",
            public_id=media_id,
            resource_type="video",
        )

    def _serialize_model_image(self, image: PortfolioImageModel) -> dict:
        return {
            "id": str(image.id),
            "secure_url": _safe_portfolio_display_url(image.cloudinary_secure_url, image.secure_url),
            "local_preview_url": None,
            "display_url": _safe_portfolio_display_url(image.cloudinary_secure_url, image.secure_url),
            "media_type": image.media_type,
            "caption": image.caption,
            "order": image.order,
            "upload_status": image.upload_status,
            "quality_status": image.quality_status,
            "visibility_status": image.visibility_status,
            "upload_error": image.upload_error,
            "failure_reason": image.failure_reason,
            "rejection_reason": image.rejection_reason,
            "original_filename": image.original_filename,
            "mime_type": image.mime_type,
            "file_size": image.file_size,
            "cloudinary_secure_url": _safe_portfolio_display_url(image.cloudinary_secure_url),
            "width": image.width,
            "height": image.height,
            "duration_seconds": image.duration_seconds,
            "analyzer_score": image.analyzer_score,
            "analyzer_summary": image.analyzer_summary,
            "is_active": image.is_active,
            "is_deleted": image.is_deleted,
        }

    def _validate_portfolio_media(self, uploaded_media) -> tuple[dict | None, str | None, dict]:
        content_type = (getattr(uploaded_media, "content_type", "") or "").lower()
        filename = uploaded_media.name or ""
        extension = Path(filename).suffix.lower()
        current_position = uploaded_media.tell() if hasattr(uploaded_media, "tell") else None
        try:
            uploaded_media.seek(0)
            header = uploaded_media.read(128)
        finally:
            try:
                uploaded_media.seek(current_position or 0)
            except Exception:
                pass

        inferred_type = self._infer_media_content_type(extension, header)
        effective_content_type = content_type if content_type in ALLOWED_PORTFOLIO_MEDIA_TYPES else inferred_type
        if not effective_content_type:
            return self._invalid_media("Only JPEG, PNG, WEBP images or MP4/WEBM videos are allowed."), None, {}

        media_type = PortfolioImageModel.MediaType.IMAGE if effective_content_type in ALLOWED_PORTFOLIO_IMAGE_TYPES else PortfolioImageModel.MediaType.VIDEO
        max_upload_size = (
            getattr(settings, "VENDOR_PORTFOLIO_MAX_UPLOAD_SIZE", 4 * 1024 * 1024)
            if media_type == PortfolioImageModel.MediaType.IMAGE
            else VIDEO_PORTFOLIO_MAX_UPLOAD_SIZE
        )
        if uploaded_media.size > max_upload_size:
            if media_type == PortfolioImageModel.MediaType.VIDEO:
                return self._invalid_media("Videos must be 10MB or smaller."), None, {}
            return self._invalid_media(f"Image file is too large. Maximum size is {max_upload_size // (1024 * 1024)}MB."), None, {}

        if media_type == PortfolioImageModel.MediaType.IMAGE:
            if extension not in {".jpg", ".jpeg", ".png", ".webp"}:
                return self._invalid_media("Only JPEG, PNG, or WEBP image files are allowed."), None, {}
            if effective_content_type != self._infer_media_content_type(extension, header):
                return self._invalid_media("Only JPEG, PNG, WEBP images or MP4/WEBM videos are allowed."), None, {}
            dimensions_error, dimensions = self._image_dimensions(uploaded_media)
            if dimensions_error:
                return dimensions_error, None, {}
            return None, media_type, dimensions

        if extension not in {".mp4", ".webm", ".mov"}:
            return self._invalid_media("Only MP4, WEBM, or MOV highlight videos are allowed."), None, {}
        if effective_content_type != self._infer_media_content_type(extension, header):
            return self._invalid_media("This video could not be read. Upload a valid MP4, WEBM, or MOV highlight video."), None, {}
        return None, media_type, {}

    def _image_dimensions(self, uploaded_media) -> tuple[dict | None, dict]:
        current_position = uploaded_media.tell() if hasattr(uploaded_media, "tell") else None
        try:
            from PIL import Image

            uploaded_media.seek(0)
            with Image.open(uploaded_media) as image:
                image.verify()
            uploaded_media.seek(0)
            with Image.open(uploaded_media) as image:
                width, height = image.size
        except Exception:
            return self._invalid_media("This image could not be read. Upload a valid image."), {}
        finally:
            try:
                uploaded_media.seek(current_position or 0)
            except Exception:
                pass
        min_width = int(getattr(settings, "VENDOR_PORTFOLIO_MIN_IMAGE_WIDTH", 800))
        min_height = int(getattr(settings, "VENDOR_PORTFOLIO_MIN_IMAGE_HEIGHT", 600))
        if width < min_width or height < min_height:
            return self._invalid_media("This image is too small. Upload a clearer, higher-resolution photo."), {}
        return None, {"width": width, "height": height}

    def _infer_media_content_type(self, extension: str, header: bytes) -> str | None:
        if extension in {".jpg", ".jpeg"} and header.startswith(b"\xff\xd8\xff"):
            return "image/jpeg"
        if extension == ".png" and header.startswith(b"\x89PNG\r\n\x1a\n"):
            return "image/png"
        if extension == ".webp" and header.startswith(b"RIFF") and header[8:12] == b"WEBP":
            return "image/webp"
        if extension in {".mp4", ".mov"} and b"ftyp" in header[:128]:
            return "video/mp4" if extension == ".mp4" else "video/quicktime"
        if extension == ".webm" and header.startswith(b"\x1aE\xdf\xa3"):
            return "video/webm"
        return None

    def _invalid_media(self, message: str) -> dict:
        return {
            "code": PORTFOLIO_MEDIA_INVALID_CODE,
            "message": PORTFOLIO_MEDIA_INVALID_MESSAGE,
            "field_errors": {"media": [message]},
        }


class PortfolioImageReorderView(APIView):
    permission_classes = [IsAuthenticated, IsVendor]

    def post(self, request):
        """Reorder portfolio images."""
        profile, error_response = _get_current_vendor_profile(request, require_workspace=True)
        if error_response:
            return error_response

        serializer = ReorderImagesSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        image_ids = [uuid.UUID(id_str) for id_str in serializer.validated_data["image_ids"]]

        cmd = ReorderPortfolioImagesCommand(
            vendor_id=profile.id,
            image_ids_in_order=image_ids
        )

        command_handlers = get_command_handlers()
        reordered = command_handlers.reorder_portfolio_images(cmd)
        return Response([PortfolioImageView._serialize_image(None, img) for img in reordered])


class ServicePackageListView(APIView):
    permission_classes = [IsAuthenticated, IsVendor]

    def get(self, request):
        """List service packages for the current vendor."""
        profile, error_response = _get_current_vendor_profile(request, require_workspace=True)
        if error_response:
            return error_response
        query_handlers = get_query_handlers()

        packages = query_handlers.list_service_packages(profile.id)
        return Response([self._serialize_package(pkg) for pkg in packages])

    def post(self, request):
        """Create a new service package."""
        profile, error_response = _get_current_vendor_profile(request, require_workspace=True)
        if error_response:
            return error_response

        serializer = ServicePackageSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        data = serializer.validated_data

        cmd = CreateServicePackageCommand(
            vendor_id=profile.id,
            name=data["name"],
            description=data["description"],
            price=data["price"],
            currency=data.get("currency", "RWF"),
            package_tier=data["package_tier"],
        )

        command_handlers = get_command_handlers()
        try:
            package = command_handlers.create_service_package(cmd)
        except PackageValidationError as exc:
            raise DRFValidationError(exc.errors)
        return Response(self._serialize_package(package), status=status.HTTP_201_CREATED)

    def _serialize_package(self, dto: ServicePackageDTO) -> dict:
        return {
            "id": str(dto.id),
            "name": dto.name,
            "description": dto.description,
            "price": str(dto.price),
            "currency": dto.currency,
            "package_tier": dto.package_tier,
            "approval_status": dto.approval_status,
            "rejection_reason": dto.rejection_reason,
            "is_active": dto.is_active,
            "is_deleted": dto.is_deleted,
            "deleted_at": dto.deleted_at.isoformat() if dto.deleted_at else None,
        }


class ServicePackageDetailView(APIView):
    permission_classes = [IsAuthenticated, IsVendor]

    def patch(self, request, package_id):
        """Update a service package."""
        profile, error_response = _get_current_vendor_profile(request, require_workspace=True)
        if error_response:
            return error_response
        query_handlers = get_query_handlers()

        # Verify ownership
        packages = query_handlers.list_service_packages(profile.id)
        pkg = next((p for p in packages if p.id == package_id), None)
        if not pkg:
            return Response(
                {"detail": "Package not found or does not belong to this vendor."},
                status=status.HTTP_404_NOT_FOUND
            )

        serializer = ServicePackageSerializer(data=request.data, partial=True)
        serializer.is_valid(raise_exception=True)
        data = serializer.validated_data

        cmd = UpdateServicePackageCommand(
            package_id=package_id,
            name=data.get("name"),
            description=data.get("description"),
            price=data.get("price"),
            currency=data.get("currency"),
            package_tier=data.get("package_tier"),
        )

        command_handlers = get_command_handlers()
        try:
            updated = command_handlers.update_service_package(cmd)
        except PackageValidationError as exc:
            raise DRFValidationError(exc.errors)
        return Response(ServicePackageListView._serialize_package(None, updated))

    def delete(self, request, package_id):
        """Deactivate a service package (soft delete)."""
        profile, error_response = _get_current_vendor_profile(request, require_workspace=True)
        if error_response:
            return error_response
        query_handlers = get_query_handlers()

        packages = query_handlers.list_service_packages(profile.id)
        pkg = next((p for p in packages if p.id == package_id), None)
        if not pkg:
            return Response(
                {"detail": "Package not found or does not belong to this vendor."},
                status=status.HTTP_404_NOT_FOUND
            )

        cmd = DeactivateServicePackageCommand(package_id=package_id, deleted_by_id=request.user.id)
        command_handlers = get_command_handlers()
        package = command_handlers.deactivate_package(cmd)
        return Response(
            {
                "message": "Package removed from active listings.",
                "package": ServicePackageListView._serialize_package(None, package),
            },
            status=status.HTTP_200_OK,
        )


class ServicePackageActivateView(APIView):
    permission_classes = [IsAuthenticated, IsVendor]

    def post(self, request, package_id):
        """Vendor packages must be approved by an administrator before publication."""
        _, error_response = _get_current_vendor_profile(request, require_workspace=True)
        if error_response:
            return error_response
        return Response(
            {"detail": "Package publication requires admin approval."},
            status=status.HTTP_403_FORBIDDEN,
        )


class InquiryListView(APIView):
    permission_classes = [IsAuthenticated, IsVendor]

    def get(self, request):
        """List inquiries for the current vendor."""
        profile, error_response = _get_current_vendor_profile(request, require_workspace=True)
        if error_response:
            return error_response
        query_handlers = get_query_handlers()

        inquiries = query_handlers.list_inquiries(profile.id)
        return Response([self._serialize_inquiry(inq) for inq in inquiries])

    def _serialize_inquiry(self, dto: InquiryDTO) -> dict:
        return {
            "id": str(dto.id),
            "client_name": dto.client_name,
            "client_email": dto.client_email,
            "client_phone": dto.client_phone,
            "message": dto.message,
            "event_date": dto.event_date.isoformat() if dto.event_date else None,
            "is_read": dto.is_read,
            "created_at": dto.created_at.isoformat(),
        }


class VendorVerificationDocumentView(APIView):
    permission_classes = [IsAuthenticated, IsVendor]
    parser_classes = [MultiPartParser, FormParser, JSONParser]

    def get(self, request):
        query_handlers = get_query_handlers()
        profile = query_handlers.get_vendor_by_user(request.user.id)
        if not profile:
            return Response(
                {
                    "code": VENDOR_PROFILE_INCOMPLETE_CODE,
                    "message": "Save your vendor profile before uploading verification documents.",
                    "detail": "No vendor profile found.",
                    "redirect_to": VENDOR_PROFILE_SETUP_REDIRECT,
                    "field_errors": {},
                    "onboarding": build_vendor_onboarding_contract(None),
                },
                status=status.HTTP_404_NOT_FOUND
            )

        documents = VerificationDocument.objects.filter(vendor_id=profile.id).order_by("-created_at")
        return Response([self._serialize_document(document) for document in documents])

    def post(self, request):
        query_handlers = get_query_handlers()
        profile = query_handlers.get_vendor_by_user(request.user.id)
        if not profile:
            return Response(
                {"detail": "No vendor profile found."},
                status=status.HTTP_404_NOT_FOUND
            )

        serializer = VerificationDocumentUploadSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)

        uploaded_document = request.FILES.get("document")
        if not uploaded_document:
            return Response(
                {"detail": "No document file provided."},
                status=status.HTTP_400_BAD_REQUEST
            )

        validation_error = self._validate_pdf(uploaded_document)
        if validation_error:
            return Response(validation_error, status=status.HTTP_400_BAD_REQUEST)

        document_id = uuid.uuid4()
        if hasattr(uploaded_document, "seek"):
            uploaded_document.seek(0)
        upload_result = CloudinaryAdapter().upload_file(
            uploaded_document,
            folder="vendor_verification_documents",
            public_id=str(document_id),
            resource_type="raw",
        )
        document = VerificationDocument.objects.create(
            id=document_id,
            vendor_id=profile.id,
            document_type=serializer.validated_data["document_type"],
            original_filename=uploaded_document.name,
            mime_type=PDF_MIME_TYPE,
            file_size=uploaded_document.size,
            secure_url=upload_result["secure_url"],
            cloudinary_public_id=upload_result["public_id"],
            cloudinary_secure_url=upload_result["secure_url"],
            upload_status=VerificationDocument.UploadStatus.QUEUED,
            verification_status=VerificationDocument.VerificationStatus.PENDING_REVIEW,
            fraud_status=VerificationDocument.FraudStatus.REVIEW_REQUIRED,
            fraud_reasons=["PDF preflight passed; awaiting admin review."],
            temp_upload_path=None,
        )

        from tasks.document_tasks import process_vendor_verification_document_task

        processing_deferred = False
        try:
            process_vendor_verification_document_task.delay(str(document.id))
        except Exception:
            processing_deferred = True
            document.upload_status = VerificationDocument.UploadStatus.PROCESSING_DEFERRED
            document.save(update_fields=["upload_status", "updated_at"])
            logger.exception(
                "Vendor verification document dispatch deferred.",
                extra={"document_id": str(document.id), "vendor_id": str(profile.id)},
            )

        return Response(
            {
                "status": "queued",
                "document_id": str(document.id),
                "processing_deferred": processing_deferred,
                "message": DOCUMENT_RECEIVED_MESSAGE,
                "onboarding": build_vendor_onboarding_contract(profile),
            },
            status=status.HTTP_202_ACCEPTED,
        )

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

        current_position = uploaded_document.tell() if hasattr(uploaded_document, "tell") else None
        try:
            uploaded_document.seek(0)
            content = uploaded_document.read()
        finally:
            try:
                uploaded_document.seek(current_position or 0)
            except Exception:
                pass

        if not content.startswith(b"%PDF"):
            return {"document": ["Verification document is not a valid PDF file."]}
        if b"%%EOF" not in content[-2048:]:
            return {"document": ["Verification document appears to be incomplete or corrupt."]}
        if b"/Encrypt" in content[:4096] or b"/Encrypt" in content:
            return {"document": ["Password-protected PDFs cannot be processed."]}
        if not self._has_pdf_page(content):
            return {"document": ["Verification document must contain at least one page."]}
        return None

    def _has_pdf_page(self, content: bytes) -> bool:
        return b"/Type /Page" in content or b"/Type/Page" in content

    def _serialize_document(self, document: VerificationDocument) -> dict:
        return {
            "id": str(document.id),
            "document_type": document.document_type,
            "original_filename": document.original_filename,
            "mime_type": document.mime_type,
            "file_size": document.file_size,
            "secure_url": document.cloudinary_secure_url or document.secure_url,
            "cloudinary_secure_url": document.cloudinary_secure_url or document.secure_url,
            "upload_status": document.upload_status,
            "verification_status": document.verification_status,
            "failure_reason": document.failure_reason,
            "odcr_status": document.odcr_status,
            "odcr_score": document.odcr_score,
            "odcr_result_summary": document.odcr_result_summary,
            "fraud_status": document.fraud_status,
            "fraud_score": document.fraud_score,
            "fraud_reasons": document.fraud_reasons,
            "created_at": document.created_at.isoformat(),
        }


class PublicVendorProfileView(APIView):
    permission_classes = [AllowAny]
    authentication_classes = []

    def get(self, request, vendor_id):
        public_portfolio = (
            PortfolioImageModel.objects.filter(
                is_active=True,
                is_deleted=False,
                upload_status=PortfolioImageModel.UploadStatus.UPLOADED,
                quality_status=PortfolioImageModel.QualityStatus.PASSED,
                visibility_status=PortfolioImageModel.VisibilityStatus.APPROVED,
            )
            .exclude(cloudinary_secure_url__isnull=True, secure_url="")
            .exclude(cloudinary_secure_url="", secure_url="")
            .order_by("order", "created_at")
        )
        public_packages = ServicePackageModel.objects.filter(
            is_active=True,
            is_deleted=False,
            approval_status=ServicePackageModel.ApprovalStatus.APPROVED,
        ).order_by("price", "created_at")
        vendor = (
            VendorProfileModel.objects.filter(id=vendor_id, status=VendorProfileModel.Status.APPROVED)
            .prefetch_related(
                Prefetch("images", queryset=public_portfolio, to_attr="public_portfolio"),
                Prefetch("packages", queryset=public_packages, to_attr="public_packages"),
            )
            .first()
        )
        if not vendor:
            return Response({"detail": "Not found."}, status=status.HTTP_404_NOT_FOUND)

        marketplace_stats = _get_public_marketplace_stats(vendor.id)
        return api_success(
            code="vendor_public_profile_loaded",
            message="Vendor profile loaded.",
            data=VendorPublicProfileSerializer(vendor, context=marketplace_stats).data,
            request=request,
        )


class PublicInquiryView(APIView):
    """Public endpoint for clients to send inquiries to a vendor (no auth required)."""
    permission_classes = [AllowAny]
    authentication_classes = []
    throttle_classes = [PublicVendorInquiryThrottle]
    throttle_scope = "public_vendor_inquiry"

    def post(self, request, vendor_id):
        if not VendorProfileModel.objects.filter(
            id=vendor_id,
            status=VendorProfileModel.Status.APPROVED,
        ).exists():
            return Response({"detail": "Not found."}, status=status.HTTP_404_NOT_FOUND)
        serializer = InquirySerializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        data = serializer.validated_data

        cmd = SendInquiryCommand(
            vendor_id=uuid.UUID(str(vendor_id)),
            client_name=data["client_name"],
            client_email=data["client_email"],
            message=data["message"],
            client_phone=data.get("client_phone"),
            event_date=data.get("event_date"),
        )

        command_handlers = get_command_handlers()
        try:
            inquiry = command_handlers.send_inquiry(cmd)
            return api_success(
                code="vendor_inquiry_created",
                message="Inquiry sent successfully.",
                data={"id": str(inquiry.id)},
                status=status.HTTP_201_CREATED,
                request=request,
            )
        except ValueError as e:
            return Response({"detail": str(e)}, status=status.HTTP_400_BAD_REQUEST)


class VendorDashboardSummaryView(APIView):
    permission_classes = [IsAuthenticated, IsVendor]

    def get(self, request):
        profile, error_response = _get_current_vendor_profile(request, require_workspace=True)
        if error_response:
            return error_response
        query_handlers = get_query_handlers()
        return Response(query_handlers.get_dashboard_summary(profile.id))


class VendorAnalyticsView(APIView):
    permission_classes = [IsAuthenticated, IsVendor]

    def get(self, request):
        profile, error_response = _get_current_vendor_profile(request, require_workspace=True)
        if error_response:
            return error_response
        query_handlers = get_query_handlers()
        return Response(query_handlers.get_analytics(profile.id))


class VendorActivityView(APIView):
    permission_classes = [IsAuthenticated, IsVendor]

    def get(self, request):
        profile, error_response = _get_current_vendor_profile(request, require_workspace=True)
        if error_response:
            return error_response
        query_handlers = get_query_handlers()
        limit, limit_error = self._activity_limit(request)
        if limit_error:
            return limit_error
        return Response(query_handlers.get_recent_activity(profile.id, limit=limit))

    def _activity_limit(self, request) -> tuple[int | None, Response | None]:
        raw_limit = request.query_params.get("limit", "10")
        try:
            limit = int(raw_limit)
        except (TypeError, ValueError):
            return None, self._invalid_limit_response(request)
        if limit < 1 or limit > 100:
            return None, self._invalid_limit_response(request)
        return limit, None

    def _invalid_limit_response(self, request) -> Response:
        return api_error(
            code="vendor_activity_limit_invalid",
            message="Activity limit must be an integer from 1 to 100.",
            field_errors={"limit": ["Enter an integer from 1 to 100."]},
            status=status.HTTP_400_BAD_REQUEST,
            request=request,
        )


class AdminPendingVendorListView(APIView):
    permission_classes = [IsAuthenticated, IsAdmin]

    def get(self, request):
        from django_app.vendors.models import VendorProfile

        pending = VendorProfile.objects.filter(status=VendorProfile.Status.PENDING_REVIEW).select_related("user")
        return Response([
            {
                "id": str(profile.id),
                "user_id": str(profile.user_id),
                "business_name": profile.business_name,
                "category": profile.category,
                "custom_category": profile.custom_category,
                "description": profile.description,
                "service_area": profile.service_area,
                "contact_email": profile.contact_email,
                "contact_phone": profile.contact_phone,
                "website": profile.website,
                "status": profile.status,
                "submitted_at": profile.submitted_at.isoformat() if profile.submitted_at else None,
                "approved_at": profile.approved_at.isoformat() if profile.approved_at else None,
                "rejected_at": profile.rejected_at.isoformat() if profile.rejected_at else None,
                "rejection_reason": profile.rejection_reason,
            }
            for profile in pending
        ])
