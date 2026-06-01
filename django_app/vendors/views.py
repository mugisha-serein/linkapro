import uuid
from rest_framework.views import APIView
from rest_framework.response import Response
from rest_framework import status
from rest_framework.permissions import IsAuthenticated
from django_app.common.permissions import IsVendor, IsAdmin
from rest_framework.parsers import MultiPartParser, FormParser, JSONParser

from .serializers import (
    VendorProfileSerializer,
    PortfolioImageSerializer,
    ServicePackageSerializer,
    InquirySerializer,
    SubmitForReviewSerializer,
    ReorderImagesSerializer,
)
from .services import get_command_handlers, get_query_handlers
from application.vendors.commands import (
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
)
from application.vendors.dtos import (
    VendorProfileDTO,
    PortfolioImageDTO,
    ServicePackageDTO,
    InquiryDTO,
)


class VendorProfileView(APIView):
    permission_classes = [IsAuthenticated, IsVendor]

    def get(self, request):
        """Get the current user's vendor profile."""
        query_handlers = get_query_handlers()
        profile = query_handlers.get_vendor_by_user(request.user.id)
        if not profile:
            return Response(
                {"detail": "No vendor profile found."},
                status=status.HTTP_404_NOT_FOUND
            )
        return Response(self._serialize_profile(profile))

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
            website=data.get("website"),
        )

        try:
            command_handlers = get_command_handlers()
            profile = command_handlers.create_profile(cmd)
            return Response(self._serialize_profile(profile), status=status.HTTP_201_CREATED)
        except ValueError as e:
            return Response({"detail": str(e)}, status=status.HTTP_400_BAD_REQUEST)

    def patch(self, request):
        """Update the current user's vendor profile."""
        query_handlers = get_query_handlers()
        profile = query_handlers.get_vendor_by_user(request.user.id)
        if not profile:
            return Response(
                {"detail": "No vendor profile found."},
                status=status.HTTP_404_NOT_FOUND
            )

        serializer = VendorProfileSerializer(data=request.data, partial=True)
        serializer.is_valid(raise_exception=True)
        data = serializer.validated_data

        cmd = UpdateVendorProfileCommand(
            vendor_id=profile.id,
            business_name=data.get("business_name"),
            description=data.get("description"),
            service_area=data.get("service_area"),
            contact_email=data.get("contact_email"),
            contact_phone=data.get("contact_phone"),
            website=data.get("website"),
        )

        try:
            command_handlers = get_command_handlers()
            updated_profile = command_handlers.update_profile(cmd)
            return Response(self._serialize_profile(updated_profile))
        except ValueError as e:
            return Response({"detail": str(e)}, status=status.HTTP_400_BAD_REQUEST)

    def _serialize_profile(self, dto: VendorProfileDTO) -> dict:
        return {
            "id": str(dto.id),
            "business_name": dto.business_name,
            "category": dto.category,
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


class VendorSubmitForReviewView(APIView):
    permission_classes = [IsAuthenticated, IsVendor]

    def post(self, request):
        """Submit the vendor profile for admin review."""
        query_handlers = get_query_handlers()
        profile = query_handlers.get_vendor_by_user(request.user.id)
        if not profile:
            return Response(
                {"detail": "No vendor profile found."},
                status=status.HTTP_404_NOT_FOUND
            )

        cmd = SubmitVendorForReviewCommand(vendor_id=profile.id)
        try:
            command_handlers = get_command_handlers()
            updated_profile = command_handlers.submit_for_review(cmd)
            return Response({
                "status": updated_profile.status,
                "submitted_at": updated_profile.submitted_at.isoformat() if updated_profile.submitted_at else None
            })
        except ValueError as e:
            return Response({"detail": str(e)}, status=status.HTTP_400_BAD_REQUEST)


class PortfolioImageView(APIView):
    permission_classes = [IsAuthenticated, IsVendor]
    parser_classes = [MultiPartParser, FormParser, JSONParser]

    def get(self, request):
        """List portfolio images for the current vendor."""
        query_handlers = get_query_handlers()
        profile = query_handlers.get_vendor_by_user(request.user.id)
        if not profile:
            return Response(
                {"detail": "No vendor profile found."},
                status=status.HTTP_404_NOT_FOUND
            )

        images = query_handlers.list_portfolio_images(profile.id)
        return Response([self._serialize_image(img) for img in images])

    def post(self, request):
        """Upload a new portfolio image (via Celery task)."""
        query_handlers = get_query_handlers()
        profile = query_handlers.get_vendor_by_user(request.user.id)
        if not profile:
            return Response(
                {"detail": "No vendor profile found."},
                status=status.HTTP_404_NOT_FOUND
            )

        if "image" not in request.FILES:
            return Response(
                {"detail": "No image file provided."},
                status=status.HTTP_400_BAD_REQUEST
            )

        # In a real implementation, we would:
        # 1. Save the uploaded file temporarily
        # 2. Dispatch a domain event that triggers a Celery task
        # 3. The Celery task uploads to Cloudinary and then calls the application handler
        # For simplicity, we'll assume synchronous upload here, but note the spec requires async.

        from infrastructure.adapters.cloudinary_adapter import CloudinaryAdapter
        adapter = CloudinaryAdapter()
        result = adapter.upload_image(request.FILES["image"])

        caption = request.data.get("caption")
        cmd = AddPortfolioImageCommand(
            vendor_id=profile.id,
            public_id=result["public_id"],
            secure_url=result["secure_url"],
            caption=caption,
        )

        command_handlers = get_command_handlers()
        image_dto = command_handlers.add_portfolio_image(cmd)
        return Response(self._serialize_image(image_dto), status=status.HTTP_201_CREATED)

    def delete(self, request, image_id):
        """Delete a portfolio image."""
        query_handlers = get_query_handlers()
        profile = query_handlers.get_vendor_by_user(request.user.id)
        if not profile:
            return Response(
                {"detail": "No vendor profile found."},
                status=status.HTTP_404_NOT_FOUND
            )

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
        }


class PortfolioImageReorderView(APIView):
    permission_classes = [IsAuthenticated, IsVendor]

    def post(self, request):
        """Reorder portfolio images."""
        query_handlers = get_query_handlers()
        profile = query_handlers.get_vendor_by_user(request.user.id)
        if not profile:
            return Response(
                {"detail": "No vendor profile found."},
                status=status.HTTP_404_NOT_FOUND
            )

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
        query_handlers = get_query_handlers()
        profile = query_handlers.get_vendor_by_user(request.user.id)
        if not profile:
            return Response(
                {"detail": "No vendor profile found."},
                status=status.HTTP_404_NOT_FOUND
            )

        packages = query_handlers.list_service_packages(profile.id)
        return Response([self._serialize_package(pkg) for pkg in packages])

    def post(self, request):
        """Create a new service package."""
        query_handlers = get_query_handlers()
        profile = query_handlers.get_vendor_by_user(request.user.id)
        if not profile:
            return Response(
                {"detail": "No vendor profile found."},
                status=status.HTTP_404_NOT_FOUND
            )

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
        query_handlers = get_query_handlers()
        profile = query_handlers.get_vendor_by_user(request.user.id)
        if not profile:
            return Response(
                {"detail": "No vendor profile found."},
                status=status.HTTP_404_NOT_FOUND
            )

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
        query_handlers = get_query_handlers()
        profile = query_handlers.get_vendor_by_user(request.user.id)
        if not profile:
            return Response(
                {"detail": "No vendor profile found."},
                status=status.HTTP_404_NOT_FOUND
            )

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
        """Reactivate a deactivated service package."""
        query_handlers = get_query_handlers()
        profile = query_handlers.get_vendor_by_user(request.user.id)
        if not profile:
            return Response(
                {"detail": "No vendor profile found."},
                status=status.HTTP_404_NOT_FOUND
            )

        packages = query_handlers.list_service_packages(profile.id)
        pkg = next((p for p in packages if str(p.id) == package_id), None)
        if not pkg:
            return Response(
                {"detail": "Package not found or does not belong to this vendor."},
                status=status.HTTP_404_NOT_FOUND
            )

        cmd = ActivateServicePackageCommand(package_id=uuid.UUID(package_id))
        command_handlers = get_command_handlers()
        activated = command_handlers.activate_package(cmd)
        return Response(ServicePackageListView._serialize_package(None, activated))


class InquiryListView(APIView):
    permission_classes = [IsAuthenticated, IsVendor]

    def get(self, request):
        """List inquiries for the current vendor."""
        query_handlers = get_query_handlers()
        profile = query_handlers.get_vendor_by_user(request.user.id)
        if not profile:
            return Response(
                {"detail": "No vendor profile found."},
                status=status.HTTP_404_NOT_FOUND
            )

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
        query_handlers = get_query_handlers()
        profile = query_handlers.get_vendor_by_user(request.user.id)
        if not profile:
            return Response({"detail": "No vendor profile found."}, status=status.HTTP_404_NOT_FOUND)
        return Response(query_handlers.get_dashboard_summary(profile.id))


class VendorAnalyticsView(APIView):
    permission_classes = [IsAuthenticated, IsVendor]

    def get(self, request):
        query_handlers = get_query_handlers()
        profile = query_handlers.get_vendor_by_user(request.user.id)
        if not profile:
            return Response({"detail": "No vendor profile found."}, status=status.HTTP_404_NOT_FOUND)
        return Response(query_handlers.get_analytics(profile.id))


class VendorActivityView(APIView):
    permission_classes = [IsAuthenticated, IsVendor]

    def get(self, request):
        query_handlers = get_query_handlers()
        profile = query_handlers.get_vendor_by_user(request.user.id)
        if not profile:
            return Response({"detail": "No vendor profile found."}, status=status.HTTP_404_NOT_FOUND)
        limit = int(request.query_params.get("limit", 10))
        return Response(query_handlers.get_recent_activity(profile.id, limit=limit))


class AdminPendingVendorListView(APIView):
    permission_classes = [IsAuthenticated, IsAdmin]

    def get(self, request):
        query_handlers = get_query_handlers()
        pending = query_handlers.list_pending_approvals()
        return Response([VendorProfileView()._serialize_profile(profile) for profile in pending])