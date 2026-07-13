from __future__ import annotations

from ..vendor_view_common import *
from ..vendor_view_common import _validation_error_response
from ..vendor_view_common import _get_current_vendor_profile
from ..vendor_view_common import _serialize_profile
from ..vendor_view_common import _actor
from ..vendor_view_common import _branding_media_error
from ..vendor_view_common import _safe_public_branding_url
from ..vendor_view_common import _infer_image_content_type
from ..vendor_view_common import _vendor_profile_incomplete_response
from ..vendor_view_common import _has_submitted_verification_document
from ..vendor_view_common import _get_public_marketplace_stats


@method_decorator(csrf_exempt, name="dispatch")
class VendorProfileView(APIView):
    permission_classes = [IsAuthenticated, IsVendor]

    def get(self, request):
        """Get the current user's vendor profile."""
        profile, error_response = _get_current_vendor_profile(request)
        if error_response:
            return error_response
        return response_with_version(Response(_serialize_profile(profile)), profile.version)

    def post(self, request):
        """Create a new vendor profile for the current user."""
        serializer = VendorProfileSerializer(data=request.data)
        if not serializer.is_valid():
            return _validation_error_response(serializer.errors)
        data = serializer.validated_data

        cmd = CreateVendorProfileCommand(
            actor=_actor(request),
            business_name=data["business_name"],
            category=data["category"],
            description=data["description"],
            service_area=data["service_area"],
            contact_email=data["contact_email"],
            contact_phone=data["contact_phone"],
            custom_category=data.get("custom_category"),
            website=data.get("website"),
            idempotency_key=request.headers.get("Idempotency-Key") or str(uuid.uuid4()),
        )

        try:
            command_handlers = get_command_handlers()
            profile = command_handlers.create_profile(cmd)
            return response_with_version(Response(
                _serialize_profile(profile, message="Vendor profile saved."),
                status=status.HTTP_201_CREATED,
            ), profile.version)
        except Exception as exc:
            mapped = map_vendor_exception(exc)
            if mapped is not None:
                return mapped
            raise

    def patch(self, request):
        """Update the current user's vendor profile."""
        profile, error_response = _get_current_vendor_profile(request)
        if error_response:
            return error_response

        serializer = VendorProfileSerializer(data=request.data, partial=True)
        if not serializer.is_valid():
            return _validation_error_response(serializer.errors, profile=profile)
        data = serializer.validated_data
        expected_version, version_error = resolve_expected_version(request)
        if version_error:
            return version_error

        def _field(name: str):
            from application.vendors.commands import OMITTED

            return data[name] if name in data else OMITTED

        cmd = UpdateVendorProfileCommand(
            actor=_actor(request),
            vendor_id=profile.id,
            expected_version=expected_version,
            business_name=_field("business_name"),
            category=_field("category"),
            description=_field("description"),
            service_area=_field("service_area"),
            contact_email=_field("contact_email"),
            contact_phone=_field("contact_phone"),
            custom_category=_field("custom_category"),
            website=_field("website"),
        )

        try:
            command_handlers = get_command_handlers()
            updated_profile = command_handlers.update_profile(cmd)
            return response_with_version(Response(_serialize_profile(updated_profile, message="Vendor profile saved.")), updated_profile.version)
        except Exception as exc:
            mapped = map_vendor_exception(exc)
            if mapped is not None:
                return mapped
            raise


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

        updated_profile = get_query_handlers().get_vendor(GetVendorQuery(actor=_actor(request), vendor_id=vendor.id))
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

        updated_profile = get_query_handlers().get_vendor(GetVendorQuery(actor=_actor(request), vendor_id=vendor.id))
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

        expected_version, version_error = resolve_expected_version(request)
        if version_error:
            return version_error

        cmd = SubmitVendorForReviewCommand(
            actor=_actor(request),
            vendor_id=profile.id,
            expected_version=expected_version,
        )
        try:
            command_handlers = get_command_handlers()
            updated_profile = command_handlers.submit_for_review(cmd)
            return response_with_version(
                Response(_serialize_profile(updated_profile, message="Profile submitted for review.")),
                updated_profile.version,
            )
        except Exception as exc:
            mapped = map_vendor_exception(exc)
            if mapped is not None:
                return mapped
            raise


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
