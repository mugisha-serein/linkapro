from __future__ import annotations

from .vendor_view_common import *


class PortfolioImageView(APIView):
    permission_classes = [IsAuthenticated, IsVendor]
    parser_classes = [MultiPartParser, FormParser, JSONParser]

    def get(self, request):
        """List portfolio images for the current vendor."""
        profile, error_response = _get_current_vendor_profile(request, require_workspace=True)
        if error_response:
            return error_response
        query_handlers = get_query_handlers()

        query = ListPortfolioImagesQuery(actor=_actor(request), vendor_id=profile.id)
        images = query_handlers.list_portfolio_images(query)
        return Response([self._serialize_image(img) for img in images.items])

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
        command_handlers = get_command_handlers()
        cmd = AddPortfolioImageCommand(
            actor=_actor(request),
            vendor_id=profile.id,
            image_id=image_id,
            public_id=shared_upload["public_id"],
            secure_url=shared_upload["secure_url"],
            caption=serializer.validated_data.get("caption") or None,
            media_type=media_type,
            upload_status=PortfolioImageModel.UploadStatus.QUEUED,
            quality_status=PortfolioImageModel.QualityStatus.PENDING_ANALYSIS,
            visibility_status=PortfolioImageModel.VisibilityStatus.PRIVATE,
            original_filename=uploaded_media.name,
            mime_type=(getattr(uploaded_media, "content_type", "") or "").lower(),
            file_size=uploaded_media.size,
            cloudinary_public_id=shared_upload["public_id"],
            cloudinary_secure_url=shared_upload["secure_url"],
            width=dimensions.get("width"),
            height=dimensions.get("height"),
            idempotency_key=request.headers.get("Idempotency-Key") or str(image_id),
        )
        try:
            created = command_handlers.add_portfolio_image(cmd)
        except Exception as exc:
            mapped = map_vendor_exception(exc)
            if mapped is not None:
                return mapped
            raise
        image = PortfolioImageModel.objects.get(id=created.id)

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
        query = ListPortfolioImagesQuery(actor=_actor(request), vendor_id=profile.id)
        images = query_handlers.list_portfolio_images(query)
        image = next((img for img in images.items if img.id == image_id), None)
        if not image:
            return vendor_error_response(
                code="vendor_portfolio_item_not_found",
                message="Image not found or does not belong to this vendor.",
                status_code=status.HTTP_404_NOT_FOUND,
            )

        expected_version, version_error = resolve_expected_version(request)
        if version_error:
            return version_error

        cmd = DeletePortfolioImageCommand(
            actor=_actor(request),
            vendor_id=profile.id,
            image_id=image_id,
            expected_version=expected_version,
        )
        command_handlers = get_command_handlers()
        try:
            command_handlers.delete_portfolio_image(cmd)
        except Exception as exc:
            mapped = map_vendor_exception(exc)
            if mapped is not None:
                return mapped
            raise
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
            "version": dto.version,
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
            "version": image.version,
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
        image_ids = [uuid.UUID(str(id_str)) for id_str in serializer.validated_data["image_ids"]]
        expected_versions = tuple(
            ResourceVersion(resource_id=uuid.UUID(str(image_id)), expected_version=version)
            for image_id, version in serializer.validated_data["expected_versions"].items()
        )

        cmd = ReorderPortfolioImagesCommand(
            actor=_actor(request),
            vendor_id=profile.id,
            image_ids_in_order=tuple(image_ids),
            expected_versions=expected_versions,
        )

        command_handlers = get_command_handlers()
        try:
            reordered = command_handlers.reorder_portfolio_images(cmd)
        except Exception as exc:
            mapped = map_vendor_exception(exc)
            if mapped is not None:
                return mapped
            raise
        return Response([PortfolioImageView._serialize_image(None, img) for img in reordered.items])
