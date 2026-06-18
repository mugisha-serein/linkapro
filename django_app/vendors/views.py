import logging
import uuid
from rest_framework.views import APIView
from rest_framework.response import Response
from rest_framework import status
from rest_framework.permissions import IsAuthenticated
from django.conf import settings
from django.core.files.storage import default_storage
from django.db.models import Max
from django.utils.decorators import method_decorator
from django.utils.text import get_valid_filename
from django.views.decorators.csrf import csrf_exempt
from django_app.common.permissions import IsVendor, IsAdmin
from rest_framework.parsers import MultiPartParser, FormParser, JSONParser

from .serializers import (
    VendorProfileSerializer,
    PortfolioImageSerializer,
    ServicePackageSerializer,
    InquirySerializer,
    SubmitForReviewSerializer,
    ReorderImagesSerializer,
    VerificationDocumentUploadSerializer,
)
from .models import PortfolioImage as PortfolioImageModel
from .models import VerificationDocument
from .models import VendorProfile as VendorProfileModel
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


VENDOR_PROFILE_INCOMPLETE_CODE = "vendor_profile_incomplete"
VENDOR_PROFILE_INCOMPLETE_DETAIL = "Vendor profile setup is required before accessing this resource."
VENDOR_PROFILE_SETUP_REDIRECT = "/vendor/profile"
VENDOR_SUSPENDED_CODE = "vendor_suspended"
VENDOR_SUSPENDED_DETAIL = "Your vendor account is suspended. Please contact support."
ALLOWED_PORTFOLIO_IMAGE_TYPES = {"image/jpeg", "image/png", "image/webp"}
PDF_MIME_TYPE = "application/pdf"
DOCUMENT_RECEIVED_MESSAGE = "Document received. Verification will continue automatically."
logger = logging.getLogger(__name__)


def _profile_completion_errors(profile: VendorProfileDTO) -> dict[str, list[str]]:
    errors: dict[str, list[str]] = {}
    for field_name in VendorProfileModel.required_profile_fields():
        value = getattr(profile, field_name, None)
        if value is None or not str(value).strip():
            errors[field_name] = ["This field is required."]
    if profile.description and len(profile.description.strip()) < 20:
        errors["description"] = ["Use at least 20 characters for your description."]
    if profile.category == VendorProfileModel.Category.OTHER and not (profile.custom_category or "").strip():
        errors["custom_category"] = ["Describe what you do when category is Other."]
    return errors


def _vendor_profile_incomplete_response(
    field_errors: dict[str, list[str]] | None = None,
) -> Response:
    return Response(
        {
            "detail": VENDOR_PROFILE_INCOMPLETE_DETAIL,
            "code": VENDOR_PROFILE_INCOMPLETE_CODE,
            "redirect_to": VENDOR_PROFILE_SETUP_REDIRECT,
            "field_errors": field_errors or {},
        },
        status=status.HTTP_403_FORBIDDEN,
    )


def _vendor_suspended_response() -> Response:
    return Response(
        {
            "detail": VENDOR_SUSPENDED_DETAIL,
            "code": VENDOR_SUSPENDED_CODE,
            "redirect_to": VENDOR_PROFILE_SETUP_REDIRECT,
        },
        status=status.HTTP_403_FORBIDDEN,
    )


def _get_current_vendor_profile(request, *, require_workspace: bool = False):
    query_handlers = get_query_handlers()
    profile = query_handlers.get_vendor_by_user(request.user.id)
    if not profile:
        return None, Response(
            {"detail": "No vendor profile found."},
            status=status.HTTP_404_NOT_FOUND,
        )
    completion_errors = _profile_completion_errors(profile)
    if require_workspace:
        if profile.status == VendorProfileModel.Status.SUSPENDED:
            return None, _vendor_suspended_response()
        if profile.status in {VendorProfileModel.Status.DRAFT, VendorProfileModel.Status.REJECTED} or completion_errors:
            return None, _vendor_profile_incomplete_response(completion_errors)
    return profile, None


def _serialize_profile(dto: VendorProfileDTO) -> dict:
    return {
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
        "status": dto.status,
        "submitted_at": dto.submitted_at.isoformat() if dto.submitted_at else None,
        "approved_at": dto.approved_at.isoformat() if dto.approved_at else None,
        "rejected_at": dto.rejected_at.isoformat() if dto.rejected_at else None,
        "rejection_reason": dto.rejection_reason,
    }


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
        serializer.is_valid(raise_exception=True)
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
            return Response(_serialize_profile(profile), status=status.HTTP_201_CREATED)
        except ValueError as e:
            return Response({"detail": str(e)}, status=status.HTTP_400_BAD_REQUEST)

    def patch(self, request):
        """Update the current user's vendor profile."""
        profile, error_response = _get_current_vendor_profile(request)
        if error_response:
            return error_response

        serializer = VendorProfileSerializer(data=request.data, partial=True)
        serializer.is_valid(raise_exception=True)
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
            return Response(_serialize_profile(updated_profile))
        except ValueError as e:
            return Response({"detail": str(e)}, status=status.HTTP_400_BAD_REQUEST)


class VendorSubmitForReviewView(APIView):
    permission_classes = [IsAuthenticated, IsVendor]

    def post(self, request):
        """Submit the vendor profile for admin review."""
        profile, error_response = _get_current_vendor_profile(request)
        if error_response:
            return error_response

        completion_errors = _profile_completion_errors(profile)
        if completion_errors:
            return _vendor_profile_incomplete_response(completion_errors)

        cmd = SubmitVendorForReviewCommand(vendor_id=profile.id)
        try:
            command_handlers = get_command_handlers()
            updated_profile = command_handlers.submit_for_review(cmd)
            return Response(_serialize_profile(updated_profile))
        except ValueError as e:
            return Response({"detail": str(e)}, status=status.HTTP_400_BAD_REQUEST)


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
        """Upload a new portfolio image (via Celery task)."""
        profile, error_response = _get_current_vendor_profile(request, require_workspace=True)
        if error_response:
            return error_response

        if "image" not in request.FILES:
            return Response(
                {"detail": "No image file provided."},
                status=status.HTTP_400_BAD_REQUEST
            )

        uploaded_image = request.FILES["image"]
        content_type = (getattr(uploaded_image, "content_type", "") or "").lower()
        if content_type not in ALLOWED_PORTFOLIO_IMAGE_TYPES:
            return Response(
                {"detail": "Unsupported image type. Upload JPEG, PNG, or WEBP images only."},
                status=status.HTTP_400_BAD_REQUEST,
            )

        max_upload_size = getattr(settings, "VENDOR_PORTFOLIO_MAX_UPLOAD_SIZE", 4 * 1024 * 1024)
        if uploaded_image.size > max_upload_size:
            return Response(
                {"detail": f"Image file is too large. Maximum size is {max_upload_size // (1024 * 1024)}MB."},
                status=status.HTTP_400_BAD_REQUEST,
            )

        serializer = PortfolioImageSerializer(data={"caption": request.data.get("caption", "")})
        serializer.is_valid(raise_exception=True)

        safe_filename = get_valid_filename(uploaded_image.name)
        temp_path = default_storage.save(
            f"vendor_portfolio_uploads/{profile.id}/{uuid.uuid4().hex}_{safe_filename}",
            uploaded_image,
        )
        max_order = PortfolioImageModel.objects.filter(vendor_id=profile.id).aggregate(Max("order"))["order__max"]
        image = PortfolioImageModel.objects.create(
            vendor_id=profile.id,
            caption=serializer.validated_data.get("caption") or None,
            order=(max_order if max_order is not None else -1) + 1,
            upload_status=PortfolioImageModel.UploadStatus.PENDING,
            original_filename=uploaded_image.name,
            temp_upload_path=temp_path,
        )

        from tasks.image_tasks import upload_vendor_portfolio_image_task

        upload_vendor_portfolio_image_task.delay(str(image.id))
        return Response(
            {
                "status": "processing",
                "job_id": str(image.id),
                "message": "Portfolio image upload is processing.",
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
        image = next((img for img in images if str(img.id) == image_id), None)
        if not image:
            return Response(
                {"detail": "Image not found or does not belong to this vendor."},
                status=status.HTTP_404_NOT_FOUND
            )

        cmd = DeletePortfolioImageCommand(image_id=uuid.UUID(image_id))
        command_handlers = get_command_handlers()
        command_handlers.delete_portfolio_image(cmd)
        return Response(status=status.HTTP_204_NO_CONTENT)

    def _serialize_image(self, dto: PortfolioImageDTO) -> dict:
        return {
            "id": str(dto.id),
            "secure_url": dto.secure_url,
            "caption": dto.caption,
            "order": dto.order,
            "upload_status": dto.upload_status,
            "upload_error": dto.upload_error,
            "original_filename": dto.original_filename,
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
        )

        command_handlers = get_command_handlers()
        package = command_handlers.create_service_package(cmd)
        return Response(self._serialize_package(package), status=status.HTTP_201_CREATED)

    def _serialize_package(self, dto: ServicePackageDTO) -> dict:
        return {
            "id": str(dto.id),
            "name": dto.name,
            "description": dto.description,
            "price": str(dto.price),
            "currency": dto.currency,
            "is_active": dto.is_active,
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
        pkg = next((p for p in packages if str(p.id) == package_id), None)
        if not pkg:
            return Response(
                {"detail": "Package not found or does not belong to this vendor."},
                status=status.HTTP_404_NOT_FOUND
            )

        serializer = ServicePackageSerializer(data=request.data, partial=True)
        serializer.is_valid(raise_exception=True)
        data = serializer.validated_data

        cmd = UpdateServicePackageCommand(
            package_id=uuid.UUID(package_id),
            name=data.get("name"),
            description=data.get("description"),
            price=data.get("price"),
        )

        command_handlers = get_command_handlers()
        updated = command_handlers.update_service_package(cmd)
        return Response(ServicePackageListView._serialize_package(None, updated))

    def delete(self, request, package_id):
        """Deactivate a service package (soft delete)."""
        profile, error_response = _get_current_vendor_profile(request, require_workspace=True)
        if error_response:
            return error_response
        query_handlers = get_query_handlers()

        packages = query_handlers.list_service_packages(profile.id)
        pkg = next((p for p in packages if str(p.id) == package_id), None)
        if not pkg:
            return Response(
                {"detail": "Package not found or does not belong to this vendor."},
                status=status.HTTP_404_NOT_FOUND
            )

        cmd = DeactivateServicePackageCommand(package_id=uuid.UUID(package_id))
        command_handlers = get_command_handlers()
        command_handlers.deactivate_package(cmd)
        return Response(status=status.HTTP_204_NO_CONTENT)


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
                {"detail": "No vendor profile found."},
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

        safe_filename = get_valid_filename(uploaded_document.name)
        temp_path = default_storage.save(
            f"vendor_verification_uploads/{profile.id}/{uuid.uuid4().hex}_{safe_filename}",
            uploaded_document,
        )
        document = VerificationDocument.objects.create(
            vendor_id=profile.id,
            document_type=serializer.validated_data["document_type"],
            original_filename=uploaded_document.name,
            mime_type=PDF_MIME_TYPE,
            file_size=uploaded_document.size,
            upload_status=VerificationDocument.UploadStatus.QUEUED,
            verification_status=VerificationDocument.VerificationStatus.PENDING_REVIEW,
            fraud_status=VerificationDocument.FraudStatus.REVIEW_REQUIRED,
            fraud_reasons=["PDF preflight passed; awaiting admin review."],
            temp_upload_path=temp_path,
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


class PublicInquiryView(APIView):
    """Public endpoint for clients to send inquiries to a vendor (no auth required)."""
    permission_classes = []  # Allow any

    def post(self, request, vendor_id):
        serializer = InquirySerializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        data = serializer.validated_data

        cmd = SendInquiryCommand(
            vendor_id=uuid.UUID(vendor_id),
            client_name=data["client_name"],
            client_email=data["client_email"],
            message=data["message"],
            client_phone=data.get("client_phone"),
            event_date=data.get("event_date"),
        )

        command_handlers = get_command_handlers()
        try:
            inquiry = command_handlers.send_inquiry(cmd)
            return Response(
                {"detail": "Inquiry sent successfully.", "id": str(inquiry.id)},
                status=status.HTTP_201_CREATED
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
        limit = int(request.query_params.get("limit", 10))
        return Response(query_handlers.get_recent_activity(profile.id, limit=limit))


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
